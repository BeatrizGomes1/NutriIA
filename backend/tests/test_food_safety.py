"""P0 safety regression tests. All integrations use in-memory fakes."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.gemini import nutrition_ai
from app.models.nutrition import AnalysisContext, Product, AnalysisStatus
from app.models.user import UserProfile
from app.services import food_safety
from app.services.food_safety import assess_food_safety, deterministic_result, NO_GUARANTEE
from app.services.analysis_provider import parse_provider_result
from app.services.database_service import product_values, product_to_domain, persist_analysis, analysis_to_domain
from app.services.nutrition_service import NutritionService
from app.services.nutrition_workflow_service import build_analysis_cache_key
from app.services.open_food_facts import OpenFoodFactsClient


def context(ingredients="water", allergies=None, restrictions=None, **kwargs):
    return AnalysisContext(product=Product(name="Product", ingredients_text=ingredients, **kwargs),
        profile={"allergies": allergies or [], "restrictions": restrictions or []})


@pytest.mark.parametrize("ingredient,target", [
    ("Leite em p\u00f3", "leite"), ("CASE\u00cdNA", "leite"), ("whey protein", "APLV"),
    ("sodium caseinate", "alergia ao leite"), ("soro de leite", "prote\u00ednas do leite"),
    ("amendoim", "amendoim"), ("peanuts", "amendoim"),
    ("Arachis hypogaea", "amendoim"), ("soy lecithin", "soja"), ("tofu", "soja"),
    ("farinha de trigo", "trigo"), ("wheat flour", "trigo"),
])
def test_direct_and_known_derived_allergens(ingredient, target):
    ctx = context(ingredient, allergies=[target])
    result = deterministic_result(ctx)
    assert result.status == "not_recommended"
    assert result.conflicts[0].category == "allergy"
    assert result.conflicts[0].profile_item == target
    assert result.conflicts[0].source_excerpt == ingredient
    assert result.evidence == [ingredient]
    assert NO_GUARANTEE in result.reasons


@pytest.mark.parametrize("ingredient,target", [("lactose", "lactose"),
    ("leite", "leite"), ("trigo", "gl\u00faten"), ("sucrose", "a\u00e7\u00facar"),
    ("cebola", "cebola")])
def test_restrictions_keep_category(ingredient, target):
    result = deterministic_result(context(ingredient, restrictions=[target]))
    assert result.status == "not_recommended"
    assert result.conflicts[0].category == "restriction"


@pytest.mark.parametrize("ingredient,target", [
    ("caseina", "lactose"), ("whey", "intoler\u00e2ncia \u00e0 lactose"),
    ("leite zero lactose", "lactose"), ("lactose", "leite"),
    ("leite de coco", "leite"), ("soy milk", "leite"),
    ("amendoimx", "amendoim"), ("milkshakeflavour", "milk"),
    ("milky", "milk"), ("sem leite", "leite"),
    ("N\u00e3o cont\u00e9m leite", "leite"), ("milk-free", "leite"),
    ("sodium lactate", "leite"), ("lecitina", "soja"), ("farinha", "trigo"),
])
def test_no_equivalence_substrings_or_unproven_sources(ingredient, target):
    assessment = assess_food_safety(context(ingredient).product, {"restrictions": [target]})
    assert not assessment.conflicts
    assert not assessment.cross_contact


def test_zero_lactose_does_not_negate_milk_protein_allergy():
    result = deterministic_result(context("leite zero lactose, caseina", allergies=["leite"]))
    assert result.status == "not_recommended"


def test_short_negative_lactose_claim_does_not_negate_casein():
    result = deterministic_result(context("sem lactose, caseina", allergies=["leite"]))
    assert result.status == "not_recommended"


@pytest.mark.parametrize("text,status", [(None, "unknown"), ("", "unknown"),
    ("ileg\u00edvel", "unknown"), ("water ...", "unknown"), ("water", "incomplete"),
    ("water", "unreadable"), ("ingredients", "unknown")])
def test_insufficient_ingredients_do_not_call_provider(text, status):
    def forbidden(_):
        raise AssertionError("provider must not override missing data")
    result = NutritionService(forbidden).analyze(
        context(text, food_safety={"ingredients_status": status}).product,
        UserProfile(allergies=["leite"]))
    assert result.status == "insufficient_information"


def test_incomplete_list_preserves_confirmed_alert_without_claiming_completeness():
    result = deterministic_result(context("leite ...", allergies=["leite"]))
    assert result.status == "not_recommended"
    assert result.conflicts
    assert any("incompleta" in reason for reason in result.reasons)


@pytest.mark.parametrize("warning", ["Pode conter leite, soja", "May contain milk",
    "Traces of milk", "produced in a facility that uses milk"])
def test_cross_contact_is_possible_not_confirmed(warning):
    result = deterministic_result(context("water; " + warning, allergies=["leite"]))
    assert result.status == "attention"
    assert result.conflicts[0].source_excerpt == warning
    assert result.conflicts[0].evidence.startswith("Poss\u00edvel contamina\u00e7\u00e3o cruzada")


def test_positive_and_cross_contact_have_separate_explanations():
    result = deterministic_result(context("leite; Pode conter soja", allergies=["leite", "soja"]))
    assert result.status == "not_recommended"
    assert len(result.conflicts) == 2
    assert result.conflicts[0].evidence.startswith("Presen\u00e7a declarada")
    assert result.conflicts[1].evidence.startswith("Poss\u00edvel")


@pytest.mark.parametrize("response", [
    {"status": "recommended", "summary": "Seguro", "conflicts": [], "evidence": []},
    "invalid JSON", {"status": "insufficient_information", "summary": "Unknown"},
])
def test_provider_cannot_remove_supported_conflicts(response):
    result = parse_provider_result(response, "gemini", context("whey", allergies=["leite"]))
    assert result.status == "not_recommended"
    assert result.conflicts[0].source_excerpt == "whey"
    assert result.summary != "Seguro"


def test_service_does_not_depend_on_provider_for_confirmed_conflict():
    def unavailable(_):
        raise RuntimeError("Gemini unavailable")
    result = NutritionService(unavailable).analyze(context("leite").product, UserProfile(allergies=["leite"]))
    assert result.status == "not_recommended"


def test_no_match_is_not_a_safety_guarantee_and_ai_prose_is_not_published():
    response = {"status": "recommended", "summary": "Seguro para alergicos",
                "reasons": ["Nao contem leite"], "evidence": []}
    result = parse_provider_result(response, "gemini", context("water", allergies=["leite"]))
    assert result.status == "attention"
    assert not result.conflicts
    assert "Seguro" not in result.summary
    assert "Nao contem leite" not in result.reasons
    assert NO_GUARANTEE in result.reasons


def test_source_excerpt_alone_does_not_prove_a_safety_relationship():
    response = {"status": "not_recommended", "summary": "Conflict", "conflicts": [
        {"term": "water", "category": "allergy", "profile_item": "leite",
         "evidence": "Water is milk", "source_excerpt": "water"}]}
    result = parse_provider_result(response, "gemini", context("water", allergies=["leite"]))
    assert result.status == "insufficient_information"
    assert not result.conflicts


def test_off_declarations_persistence_and_analysis_keep_evidence_and_nutrition():
    payload = {"status": 1, "product": {"product_name": "Product", "ingredients_text": "water",
        "allergens": "en:milk", "traces": "en:soybeans", "nutrition_data_per": "serving",
        "serving_size": "200 ml", "nutriments": {"proteins_serving": 3}}}
    client = OpenFoodFactsClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    product = client.get_product("12345678")
    row = SimpleNamespace(id=uuid4(), **product_values(product))
    restored = product_to_domain(row)
    assert restored.nutrition == product.nutrition
    assert restored.food_safety == product.food_safety
    result = NutritionService(lambda _: None).analyze(restored, UserProfile(allergies=["leite", "soja"]))
    assert result.status == "not_recommended"
    assert {c.source_excerpt for c in result.conflicts} == {"en:milk", "en:soybeans"}
    assert "food_safety" in row.nutrition_table
    assert restored.nutrition.basis == "per_serving"


def test_photo_extracts_completeness_and_separate_declarations(monkeypatch):
    payload = {"name": "Product", "ingredients_text": "water", "food_safety": {
        "ingredients_status": "incomplete", "allergen_statement": "Contem leite",
        "cross_contact_statement": "Pode conter soja"},
        "nutrition": {"basis": "per_100ml", "protein_g": 2}}
    monkeypatch.setattr(nutrition_ai, "generate_image_response", lambda *_: json.dumps(payload))
    extracted = nutrition_ai.extract_product_from_label(b"image", "image/png")
    restored = product_to_domain(SimpleNamespace(id=uuid4(), **product_values(extracted)))
    result = deterministic_result(AnalysisContext(product=restored,
        profile={"allergies": ["leite", "soja"]}))
    assert result.status == "not_recommended"
    assert len(result.conflicts) == 2
    assert any("incompleta" in reason for reason in result.reasons)
    assert restored.nutrition.basis == "per_100ml"


def test_cache_includes_profile_rules_and_source_declarations(monkeypatch):
    uid = uuid4()
    product = context("water").product
    profile = UserProfile(allergies=["leite"])
    def key(p=product, u=profile):
        return build_analysis_cache_key(uid, p, u, provider="mock", model="m", prompt_version="v")
    original = key()
    assert original != key(u=UserProfile(allergies=["soja"]))
    assert original != key(u=UserProfile(restrictions=["leite"]))
    assert original != key(p=context("water", food_safety={"cross_contact_statement": "Pode conter leite"}).product)
    assert original != key(p=context("water", food_safety={"ingredients_status": "incomplete"}).product)
    monkeypatch.setattr(food_safety, "RULES_VERSION", "next-version")
    assert original != key()


def test_persisted_alerts_keep_direct_and_possible_evidence_without_database():
    result = deterministic_result(context("leite; Pode conter soja", allergies=["leite", "soja"]))
    class Session:
        def add(self, row):
            self.row = row
        def flush(self):
            pass
    session = Session()
    product = SimpleNamespace(id=uuid4(), name="Product")
    row = persist_analysis(session, user_id=uuid4(), product=product, result=result, cache_key="x")
    row.product = product
    row.id, row.created_at = uuid4(), datetime.now(timezone.utc)
    restored = analysis_to_domain(row)
    assert restored.status == result.status
    assert {(c.source_excerpt, c.evidence) for c in restored.conflicts} == {
        (c.source_excerpt, c.evidence) for c in result.conflicts}


@pytest.mark.parametrize("text", ["leite; traces of soy", "leite, traces of soy",
    "leite, produzido em equipamento com soja"])
def test_warning_scope_does_not_downgrade_an_earlier_confirmed_ingredient(text):
    result = deterministic_result(context(text, allergies=["leite", "soja"]))
    assert result.status == "not_recommended"
    assert any(c.profile_item == "leite" and c.evidence.startswith("Presen\u00e7a") for c in result.conflicts)
    assert any(c.profile_item == "soja" and c.evidence.startswith("Poss\u00edvel") for c in result.conflicts)


def test_a_specific_derivative_restriction_is_not_expanded_to_all_milk_derivatives():
    assert not assess_food_safety(context("whey").product, {"restrictions": ["caseina"]}).conflicts


def test_original_text_takes_precedence_over_normalized_ingredient_list():
    product = Product(name="Product", ingredients_text="Pode conter leite", ingredients=["leite"])
    assessment = assess_food_safety(product, {"allergies": ["leite"]})
    assert assessment.cross_contact
    assert not assessment.conflicts


def test_old_cache_key_without_rule_version_is_never_reused():
    import hashlib
    ctx = context("water")
    uid = uuid4()
    profile = UserProfile(allergies=["leite"])
    old_payload = {"nutrition_schema_version": 2, "user_id": str(uid), "product": {
        "ean": ctx.product.ean, "name": ctx.product.name, "brand": ctx.product.brand,
        "ingredients": ctx.product.ingredients, "ingredients_text": ctx.product.ingredients_text,
        "serving_information": ctx.product.serving_information,
        "nutrition": ctx.product.nutrition.model_dump(mode="json")},
        "profile": {"goal": None, "allergies": ["leite"], "restrictions": [], "preferences": []},
        "provider": "mock", "model": "m", "prompt_version": "v"}
    old = hashlib.sha256(json.dumps(old_payload, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()
    new = build_analysis_cache_key(uid, ctx.product, profile, provider="mock", model="m", prompt_version="v")
    assert new != old


@pytest.mark.parametrize("text,profile", [("casein", "caseina"), ("caseina", "casein"),
    ("soro de leite", "whey"), ("whey", "soro de leite")])
def test_specific_derivative_synonyms_are_supported_without_broadening_target(text, profile):
    result = deterministic_result(context(text, restrictions=[profile]))
    assert result.status == "not_recommended"


def test_semicolon_does_not_turn_warning_list_into_confirmed_presence():
    result = deterministic_result(context("water; Pode conter leite; soja", allergies=["leite", "soja"]))
    assert result.status == "attention"
    assert len(result.conflicts) == 2
    assert all(c.evidence.startswith("Poss\u00edvel") for c in result.conflicts)


@pytest.mark.parametrize("text", ["leite de coco, leite", "soy milk, milk"])
def test_plant_drink_does_not_mask_an_additional_milk_ingredient(text):
    result = deterministic_result(context(text, allergies=["leite"]))
    assert result.status == "not_recommended"
    assert result.conflicts[0].source_excerpt in {"leite", "milk"}


def test_unknown_profile_term_requires_literal_evidence_and_preferences_are_not_allergies():
    product = context("water").product
    assert not assess_food_safety(product, {"allergies": ["castanha"]}).conflicts
    assert not assess_food_safety(context("leite").product, {"preferences": ["leite"]}).conflicts


def test_off_safety_only_update_preserves_existing_nutrition_in_upsert_sql():
    from sqlalchemy.dialects import postgresql
    from app.db.models import UserProfileRecord, ProductRecord
    from app.models.nutrition import AnalysisResult
    from app.services.nutrition_workflow_service import NutritionWorkflowService

    product_id, user_id = uuid4(), uuid4()
    saved = SimpleNamespace(id=product_id, ean="12345678", name="Product", brand=None,
        ingredients_raw="water", ingredients_normalized=["water"], serving_information=None,
        nutrition_table={"schema_version": 2, "values": {"basis": "per_100ml", "protein_g": 2}})
    statements = []
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def begin(self):
            return self
        def get(self, model, _):
            return object() if model is UserProfileRecord else saved
        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(one=lambda: saved)
        def add(self, row):
            row.id = uuid4()
        def flush(self):
            pass
    class Source:
        def get_product(self, _):
            return context("water", food_safety={"allergen_statement": "Contem leite"}).product
    workflow = NutritionWorkflowService(session_factory=Session, open_food_facts=Source(),
                                         nutrition_service=NutritionService(lambda _: None))
    workflow.analyze_product = lambda *_, **kwargs: AnalysisResult(status="attention", summary="Test")
    outcome = workflow.capture_ean(user_id, "12345678")
    compiled = statements[0].compile(dialect=postgresql.dialect())
    update_sql = str(compiled).split("DO UPDATE SET", 1)[1]
    assert "coalesce(products.nutrition_table" in update_sql
    assert "||" in update_sql
    assert {"food_safety": {"allergen_statement": "Contem leite"}} in compiled.params.values()
    assert outcome.product.nutrition.basis == "per_100ml"
    assert outcome.product.nutrition.protein_g == 2


@pytest.mark.parametrize("ingredients,expected", [
    ("leite de soja", False),
    ("leite de soja, leite em p\u00f3", True),
    ("bebida vegetal com case\u00edna", True),
    ("zero lactose com prote\u00edna do leite", True),
    ("leite de soja com leite", True),
    ("soy milk with milk", True),
    ("leite de soja (leite)", True),
])
def test_revision_plant_names_do_not_hide_true_dairy(ingredients, expected):
    assessment = assess_food_safety(context(ingredients).product, {"allergies": ["leite"]})
    assert bool(assessment.conflicts) is expected
    if expected:
        result = assessment.result(context(ingredients, allergies=["leite"]))
        assert result.status == "not_recommended"
        assert all(c.source_excerpt in ingredients for c in result.conflicts)


def test_revision_confirmed_conflict_precedes_missing_data_and_preserves_all_evidence():
    ctx = context("caseina ...; Pode conter soja", allergies=["leite", "soja"],
                  food_safety={"ingredients_status": "incomplete"})
    ctx.blocking_reasons = ["Lista parcialmente visivel"]
    assessment = assess_food_safety(ctx.product, ctx.profile)
    result = assessment.result(ctx)
    assert result.status == "not_recommended"
    assert "Lista parcialmente visivel" in result.reasons
    assert all(reason in result.reasons for reason in assessment.insufficient_reasons)
    assert result.conflicts == [*assessment.conflicts, *assessment.cross_contact]
    assert result.evidence == list(dict.fromkeys(c.source_excerpt for c in result.conflicts))
    assert all(c.evidence in result.reasons for c in result.conflicts)


def test_revision_rules_invalidate_v1_cache_keys(monkeypatch):
    uid = uuid4()
    ctx = context("leite ...", allergies=["leite"])
    profile = UserProfile(allergies=["leite"])
    def key():
        return build_analysis_cache_key(uid, ctx.product, profile,
                                        provider="mock", model="m", prompt_version="v")
    current = key()
    monkeypatch.setattr(food_safety, "RULES_VERSION", "food-safety-v1")
    assert current != key()


def test_revision_incomplete_data_without_confirmed_conflict_remains_insufficient():
    ctx = context("water; Pode conter leite", allergies=["leite"],
                  food_safety={"ingredients_status": "incomplete"})
    result = deterministic_result(ctx)
    assert result.status == "insufficient_information"
    assert result.conflicts[0].source_excerpt == "Pode conter leite"
    assert result.evidence == ["Pode conter leite"]
