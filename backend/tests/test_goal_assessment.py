"""Evidence-based composition evaluation, without diet or intake prescriptions."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from pydantic import ValidationError

from app.models.nutrition import NutritionFacts, Product, AnalysisContext
from app.models.user import UserProfile
from app.services.goal_assessment import assess_goal
from app.services.nutrition_service import NutritionService
from app.services.analysis_provider import parse_provider_result
from app.services.nutrition_observations import observation_catalog
from app.services.database_service import product_values, product_to_domain
from app.services.open_food_facts import OpenFoodFactsClient
from app.gemini import nutrition_ai


def facts(**kwargs):
    return NutritionFacts(basis="per_100g", **kwargs)


@pytest.mark.parametrize("protein,level", [(0, "below_source"), (2.999, "below_source"),
    (3, "source"), (4.999, "source"), (5, "high"), (10, "high")])
def test_protein_classification_uses_documented_energy_share_boundaries(protein, level):
    result = assess_goal(facts(calories_kcal=100, protein_g=protein), "muscle_gain")
    assert result.findings["protein"] == level
    assert result.metrics["protein_energy_percent"] == Decimal(str(protein)) * 4
    assert any("12%" in text and "20%" in text for text in result.observations)


def test_same_protein_with_different_calories_changes_evaluation():
    lean = assess_goal(facts(calories_kcal=100, protein_g=10), "muscle_gain")
    dense = assess_goal(facts(calories_kcal=400, protein_g=10), "muscle_gain")
    assert lean.findings["protein"] == "high"
    assert dense.findings["protein"] == "below_source"
    assert lean.observations != dense.observations


def test_changing_goal_changes_metrics_and_criteria_not_just_goal_name():
    data = facts(calories_kcal=200, protein_g=10, fiber_g=6)
    muscle, loss = (assess_goal(data, goal) for goal in ("muscle_gain", "weight_loss"))
    assert "protein_energy_percent" in muscle.metrics
    assert "protein_energy_percent" not in loss.metrics
    assert "energy_kcal_per_100g" in loss.metrics
    assert "fibre" in loss.findings
    assert "fibre" not in muscle.findings


@pytest.mark.parametrize("energy,fibre,level", [(200, 0, "not_established"), (200, 3, "source"),
    (200, 6, "high"), (50, 1.5, "high"), (100, 1.5, "source")])
def test_fibre_uses_mass_or_energy_reference_without_arbitrary_cutoffs(energy, fibre, level):
    result = assess_goal(facts(calories_kcal=energy, fiber_g=fibre), "weight_loss")
    assert result.findings["fibre"] == level


def test_energy_density_is_measured_without_high_low_cutoff_or_weight_loss_guarantee():
    lower = assess_goal(facts(calories_kcal=40), "weight_loss")
    higher = assess_goal(facts(calories_kcal=400), "weight_loss")
    assert lower.metrics["energy_kcal_per_100g"] == 40
    assert higher.metrics["energy_kcal_per_100g"] == 400
    assert lower.findings["energy_density"] == higher.findings["energy_density"] == "measured"
    assert lower.observations != higher.observations
    assert "fiber_g" in lower.missing


@pytest.mark.parametrize("basis,unit", [("per_100g", "g"), ("per_100ml", "ml")])
def test_serving_is_calculated_only_with_same_dimension(basis, unit):
    data = NutritionFacts(basis=basis, protein_g=20, calories_kcal=200,
                          fiber_g=6, serving_quantity=30, serving_unit=unit)
    result = assess_goal(data, "muscle_gain")
    assert result.metrics["serving_protein_g"] == 6
    assert result.metrics["serving_calories_kcal"] == 60
    assert result.metrics["serving_fiber_g"] == Decimal("1.8")
    assert data.protein_g == 20 and data.calories_kcal == 200
    assert any("N\u00e3o \u00e9 recomenda\u00e7\u00e3o" in text for text in result.observations)


def test_no_mass_volume_conversion():
    data = NutritionFacts(basis="per_100ml", calories_kcal=100, protein_g=5,
                          serving_quantity=30, serving_unit="g")
    result = assess_goal(data, "muscle_gain")
    assert "serving_protein_g" not in result.metrics


def test_per_serving_can_assess_ratio_but_cannot_infer_density_without_size():
    data = NutritionFacts(basis="per_serving", protein_g=10, calories_kcal=100, fiber_g=3)
    assert assess_goal(data, "muscle_gain").findings["protein"] == "high"
    loss = assess_goal(data, "weight_loss")
    assert not any("energy_kcal_per_100" in key for key in loss.metrics)
    assert loss.metrics["fibre_g_per_100kcal"] == 3


def test_known_serving_size_allows_density_without_assuming_100g_column():
    data = NutritionFacts(basis="per_serving", calories_kcal=60, fiber_g=3,
                          serving_quantity=30, serving_unit="g")
    result = assess_goal(data, "weight_loss")
    assert result.metrics["energy_kcal_per_100g"] == 200
    assert result.metrics["fibre_g_per_100g"] == 10
    assert data.basis == "per_serving" and data.calories_kcal == 60


@pytest.mark.parametrize("goal", ["muscle_gain", "weight_loss"])
def test_unknown_basis_never_produces_quantitative_metrics(goal):
    result = assess_goal(NutritionFacts(protein_g=20, calories_kcal=100, fiber_g=3), goal)
    assert not result.metrics and not result.findings
    assert result.state == "insufficient"
    assert all("20" not in text and "100" not in text for text in result.observations)


@pytest.mark.parametrize("data", [{"protein_g": -1}, {"fiber_g": float("nan")},
    {"calories_kcal": float("inf")}, {"protein_g": True}, {"fiber_g": "6"}])
def test_invalid_quantities_are_rejected_at_boundary_and_cannot_be_evaluated(data):
    with pytest.raises(ValidationError):
        facts(**data)
    constructed = NutritionFacts.model_construct(basis="per_100g", **data)
    result = assess_goal(constructed, "muscle_gain")
    assert result.state == "inconsistent" and not result.metrics


@pytest.mark.parametrize("data", [{"protein_g": 101}, {"protein_g": 20, "calories_kcal": 10},
    {"fiber_g": 7, "calories_kcal": 1}, {"protein_g": 20, "fiber_g": 20, "calories_kcal": 100},
    {"carbohydrates_g": 1, "sugars_g": 2}])
def test_inconsistent_composition_produces_no_calculations(data):
    for goal in ("muscle_gain", "weight_loss"):
        result = assess_goal(facts(**data), goal)
        assert result.state == "inconsistent" and not result.metrics


def test_missing_data_and_zero_energy_do_not_create_division_or_fake_fibre():
    for data in (facts(), facts(calories_kcal=0, protein_g=0)):
        result = assess_goal(data, "muscle_gain")
        assert "protein_energy_percent" not in result.metrics
    loss = assess_goal(facts(calories_kcal=100), "weight_loss")
    assert "fiber_g" in loss.missing and "fibre" not in loss.findings


def test_milk_conflict_still_wins_over_high_protein_evaluation():
    product = Product(name="Milk", ingredients_text="milk", nutrition=facts(calories_kcal=100, protein_g=20))
    result = NutritionService(lambda _: pytest.fail("Gemini must not be called")).analyze(
        product, UserProfile(goal="muscle_gain", allergies=["leite"]))
    assert result.status == "not_recommended" and result.conflicts
    assert any("80%" in text for text in result.reasons)


def test_untrusted_ai_numbers_cannot_override_deterministic_goal_evaluation():
    ctx = AnalysisContext(product=Product(name="Food", ingredients_text="water",
        nutrition=facts(calories_kcal=100, protein_g=5)), profile={"goal": "muscle_gain"})
    result = parse_provider_result({"status": "recommended", "summary": "Coma 500g para ganhar massa",
        "reasons": ["900 g de proteina"]}, "gemini", ctx)
    assert result.status == "attention"
    assert any("20%" in text for text in result.reasons)
    assert "500g" not in str(result) and "900 g" not in str(result)


def test_inconsistent_values_are_not_reintroduced_by_observation_catalog():
    ctx = AnalysisContext(product=Product(name="Food", ingredients_text="water",
        nutrition=facts(calories_kcal=10, protein_g=20)), profile={"goal": "muscle_gain"})
    result = parse_provider_result({"status": "recommended", "summary": "Safe"}, "gemini", ctx)
    assert result.status == "insufficient_information"
    assert not any("20 g" in text or "800%" in text for text in result.reasons)


def test_fibre_off_photo_and_jsonb_persistence_keep_original_column(monkeypatch):
    product = OpenFoodFactsClient._to_product({"nutrition_data_per": "serving", "serving_size": "30 g",
        "nutriments": {"fiber_serving": 3, "energy-kcal_serving": 60, "fiber_100g": 99}}, "12345678")
    assert product.nutrition.fiber_g == 3 and product.nutrition.basis == "per_serving"
    restored = product_to_domain(SimpleNamespace(id=uuid4(), **product_values(product)))
    assert restored.nutrition == product.nutrition
    monkeypatch.setattr(nutrition_ai, "generate_image_response", lambda *_: json.dumps({
        "name": "Food", "nutrition": {"fiber_g": 3, "basis": "per_100g"}}))
    assert nutrition_ai.extract_product_from_label(b"photo", "image/png").nutrition.fiber_g == 3


def test_assessment_has_explicit_reference_and_does_not_propose_serving_sizes():
    result = assess_goal(facts(calories_kcal=100, protein_g=5), "muscle_gain")
    assert "1924/2006" in result.reference
    assert all("Consuma" not in text and "Coma" not in text for text in result.observations)
    assert "serving_protein_g" not in result.metrics


def test_equivalent_serving_and_100g_columns_produce_same_characteristics():
    full = facts(calories_kcal=200, protein_g=20, fiber_g=6)
    portion = NutritionFacts(basis="per_serving", calories_kcal=60, protein_g=6, fiber_g=1.8,
                             serving_quantity=30, serving_unit="g")
    for goal in ("muscle_gain", "weight_loss"):
        a, b = assess_goal(full, goal), assess_goal(portion, goal)
        assert a.findings == b.findings
        for key in a.metrics.keys() & b.metrics.keys():
            if not key.startswith("serving_"):
                assert a.metrics[key] == b.metrics[key]


def test_positive_small_values_are_not_reported_as_zero_by_rounding():
    result = assess_goal(facts(calories_kcal=1, protein_g=.000001), "muscle_gain")
    assert result.metrics["protein_energy_percent"] > 0
    assert "cerca de 0%" not in result.observations[0]


def test_missing_energy_does_not_turn_unmet_mass_fibre_reference_into_definitive_absence():
    result = assess_goal(facts(fiber_g=1), "weight_loss")
    assert result.findings["fibre"] == "not_established"
    assert any("n\u00e3o demonstram" in r for r in result.observations)


@pytest.mark.parametrize("serving", ["-30 g", "- 30 g", "\u221230 g", "1e3 g"])
def test_malformed_portion_from_off_never_enables_density_calculations(serving):
    product = OpenFoodFactsClient._to_product({"nutrition_data_per": "serving", "serving_size": serving,
        "nutriments": {"energy-kcal_serving": 100}}, "12345678")
    result = assess_goal(product.nutrition, "weight_loss")
    assert product.nutrition.serving_quantity is None
    assert not any(key.startswith("energy_kcal_per_100") for key in result.metrics)
