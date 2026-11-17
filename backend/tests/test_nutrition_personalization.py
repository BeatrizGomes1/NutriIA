"""Personalization must coexist with the deterministic P0 safety rules."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.nutrition import AnalysisContext, Product
from app.models.user import UserProfile
from app.services.analysis_provider import GeminiAnalysisProvider, parse_provider_result
from app.services.database_service import persist_analysis, analysis_to_domain
from app.services.nutrition_service import NutritionService
from app.services.nutrition_observations import observation_catalog
from app.services.nutrition_workflow_service import build_analysis_cache_key
from app.services import nutrition_observations


def context(basis="unknown", allergy="Gl\u00faten"):
    return AnalysisContext(product=Product(name="Leite Integral Zero Lactose", ean="7896048706126",
        ingredients_text="Leite integral, enzima lactase, lecitina de soja",
        nutrition={"basis": basis, "protein_g": 24.6, "sodium_mg": 369.23}),
        profile={"goal": "muscle_gain", "allergies": [allergy], "restrictions": [],
                 "preferences": ["Sem lactose", "Baixo s\u00f3dio"]})


def response(status="attention", **kwargs):
    return {"status": status, "summary": "Provider summary", "reasons": [], **kwargs}


@pytest.mark.parametrize("status", ["recommended", "attention", "not_recommended", "insufficient_information"])
def test_gluten_allergy_does_not_erase_verified_nutrition_for_any_provider_status(status):
    result = parse_provider_result(response(status), "gemini", context())
    assert result.status == "attention"
    assert any("ganho de massa muscular" in r for r in result.reasons)
    assert any("Zero Lactose" in r and "Sem lactose" in r for r in result.reasons)
    assert any("Baixo s\u00f3dio" in r for r in result.reasons)
    assert not result.conflicts
    assert "cobertura" not in " ".join(result.reasons)


@pytest.mark.parametrize("basis", ["unknown", "per_100g", "per_100ml", "per_serving"])
def test_confirmed_milk_conflict_precedes_nutrition_and_keeps_both(basis):
    ctx = context(basis, allergy="leite")
    result = parse_provider_result(response("recommended", summary="Seguro para alergicos"), "gemini", ctx)
    assert result.status == "not_recommended"
    assert result.conflicts
    assert all(c.profile_item == "leite" for c in result.conflicts)
    assert any("ganho de massa muscular" in r for r in result.reasons)
    assert "Seguro para alergicos" not in result.summary


def test_service_does_not_call_gemini_but_still_includes_nutrition_for_milk_allergy():
    def forbidden(_):
        raise AssertionError("Safety must not depend on provider availability")
    ctx = context(allergy="leite")
    result = NutritionService(forbidden).analyze(ctx.product, UserProfile(**ctx.profile))
    assert result.status == "not_recommended"
    assert result.conflicts and any("Baixo s\u00f3dio" in r for r in result.reasons)


def test_unknown_basis_rejects_quantities_comparisons_clinical_promises_and_safety_guarantees():
    fake = response("recommended", summary="Seguro para alergicos, 999 g de proteina por porcao",
                    reasons=["99 mg de sodio por 100 g; baixo sodio", "Cura alergia e garante hipertrofia"])
    result = parse_provider_result(fake, "gemini", context())
    texts = result.summary + " ".join(result.reasons)
    for forbidden in ("999", "99 mg", "369", "24.6", "24,6", "por 100 g", "Cura", "Seguro para alergicos"):
        assert forbidden not in texts
    assert any("refer\u00eancia" in r and "desconhecida" in r for r in result.reasons)
    assert any("prote\u00edna informada" in r for r in result.reasons)


@pytest.mark.parametrize("basis,label", [("per_100g", "por 100 g"), ("per_100ml", "por 100 ml"),
                                         ("per_serving", "por por\u00e7\u00e3o")])
def test_known_basis_displays_only_original_quantities_without_conversions(basis, label):
    result = parse_provider_result(response(), "gemini", context(basis))
    assert any("369.23 mg" in r and label in r for r in result.reasons)
    assert any("24.6 g" in r and label in r for r in result.reasons)
    assert not result.conflicts


def test_low_sodium_is_not_a_conflict_with_milk_ingredient():
    ctx = context("per_100g")
    fake = response(conflicts=[{"term": "Leite integral", "category": "preference",
        "profile_item": "Baixo s\u00f3dio", "source_excerpt": "Leite integral",
        "evidence": "Leite integral e um ingrediente proibido para baixo sodio"}])
    result = parse_provider_result(fake, "gemini", ctx)
    assert not result.conflicts
    assert any("n\u00e3o pela presen\u00e7a isolada" in r for r in result.reasons)


def test_lactase_alone_does_not_confirm_zero_lactose():
    ctx = context()
    ctx.product.name = "Leite integral"
    result = parse_provider_result(response(), "gemini", ctx)
    assert any("sozinha" in r and "n\u00e3o confirma" in r for r in result.reasons)
    assert not any("O produto declara" in r for r in result.reasons)


def test_valid_provider_observation_selection_and_text_are_preserved():
    ctx = context()
    fact = observation_catalog(ctx)["preference:0"]["text"]
    result = parse_provider_result(response(summary=fact, reasons=[fact],
        nutrition_observation_ids=["preference:0", "nonexistent:999"]), "gemini", ctx)
    assert result.reasons[0] == fact
    assert result.summary.startswith(fact)
    assert "nonexistent:999" not in str(result)
    assert any("ganho de massa muscular" in r for r in result.reasons)


def test_adapter_supplies_fact_catalog_without_changing_public_product_fields(monkeypatch):
    from app.gemini import nutrition_ai
    captured = {}
    def generate(payload):
        captured.update(payload)
        return "{}"
    monkeypatch.setattr(nutrition_ai, "generate_product_analysis", generate)
    GeminiAnalysisProvider()(context())
    assert captured["profile"]["goal"] == "muscle_gain"
    assert any(item["id"] == "goal" for item in captured["nutrition_observations"])
    assert captured["product"]["nutrition"]["basis"] == "unknown"


def test_unverified_safety_claim_keeps_insufficient_status_without_erasing_nutrition():
    fake = response("not_recommended", conflicts=[{"term": "lactase", "category": "allergy",
        "profile_item": "Gl\u00faten", "source_excerpt": "enzima lactase", "evidence": "Lactase is gluten"}])
    result = parse_provider_result(fake, "gemini", context())
    assert result.status == "insufficient_information"
    assert not result.conflicts
    assert any("ganho de massa muscular" in r for r in result.reasons)


def test_missing_ingredients_stay_insufficient_even_with_personalization():
    ctx = context()
    ctx.product.ingredients_text = None
    result = NutritionService(lambda _: pytest.fail("Provider must not run")).analyze(
        ctx.product, UserProfile(**ctx.profile))
    assert result.status == "insufficient_information"


def test_persistence_roundtrip_keeps_safety_and_nutrition_together():
    result = parse_provider_result(response(), "gemini", context(allergy="leite"))
    class Session:
        def add(self, _): pass
        def flush(self): pass
    product = SimpleNamespace(id=uuid4(), name="Leite Integral Zero Lactose")
    row = persist_analysis(Session(), user_id=uuid4(), product=product, result=result, cache_key="new-policy")
    row.id, row.created_at, row.product = uuid4(), datetime.now(timezone.utc), product
    restored = analysis_to_domain(row)
    assert restored.status == "not_recommended"
    assert restored.reasons == result.reasons
    assert restored.conflicts == result.conflicts


def test_cache_key_changes_with_personalization_policy(monkeypatch):
    ctx = context()
    uid, profile = uuid4(), UserProfile(**ctx.profile)
    def key():
        return build_analysis_cache_key(uid, ctx.product, profile, provider="gemini", model="m", prompt_version="v")
    original = key()
    monkeypatch.setattr(nutrition_observations, "PERSONALIZATION_VERSION", "next-personalization")
    assert original != key()


@pytest.mark.parametrize("name", ["Leite n\u00e3o zero lactose", "Leite not lactose-free", "Leite pseudozero lactose"])
def test_nonpositive_lactose_claim_is_not_presented_as_a_label_declaration(name):
    ctx = context()
    ctx.product.name = name
    result = parse_provider_result(response(), "gemini", ctx)
    assert not any("O produto declara" in r for r in result.reasons)


@pytest.mark.parametrize("protein", [0, None])
def test_missing_or_zero_protein_does_not_generate_positive_protein_statement(protein):
    ctx = context()
    ctx.product.nutrition.protein_g = protein
    result = parse_provider_result(response(), "gemini", ctx)
    assert not any("prote\u00edna informada" in r for r in result.reasons)
