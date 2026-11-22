"""Regression fixture from OFF: Ninho 7891000325858, no live network needed."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.services.open_food_facts import OpenFoodFactsClient
from app.services.goal_assessment import assess_goal
from app.services.database_service import product_values, product_to_domain
from app.services.nutrition_workflow_service import build_analysis_cache_key
from app.models.user import UserProfile
from app.models.nutrition import NutritionBasis


def ninho():
    return {"product_name": "LEITE PO NINHO INTEGRAL", "nutrition_data_per": "100g",
            "ingredients_text": "Leite integral, minerais e vitaminas", "allergens": "milk",
            "serving_size": "25g", "serving_quantity": 25,
            "nutriments": {"proteins_100g": 25.2, "energy-kcal_100g": 496, "fiber_100g": 0,
                           "proteins_serving": 6.3, "energy-kcal_serving": 124, "fiber_serving": 0}}


def test_ninho_uses_one_explicit_serving_column_and_evaluates_protein_share():
    product = OpenFoodFactsClient._to_product(ninho(), "7891000325858")
    facts = product.nutrition
    assert facts.basis == "per_serving"
    assert (facts.serving_quantity, facts.serving_unit) == (25, "g")
    assert (facts.protein_g, facts.calories_kcal, facts.fiber_g) == (6.3, 124, 0)
    result = assess_goal(facts, "muscle_gain")
    assert result.metrics["protein_energy_percent"] == Decimal("6.3") * 400 / 124
    assert any("20.32%" in r for r in result.observations)
    restored = product_to_domain(SimpleNamespace(id=uuid4(), **product_values(product)))
    assert restored.nutrition == facts


@pytest.mark.parametrize("portion", [None, "", "1 scoop", "-25g", "25g / 100ml"])
def test_serving_without_reliable_portion_does_not_resolve_ambiguous_100g(portion):
    data = ninho()
    data["serving_size"] = portion
    facts = OpenFoodFactsClient._to_product(data, "12345678").nutrition
    assert facts.basis == "unknown"
    assert not assess_goal(facts, "muscle_gain").metrics


def test_serving_nutrients_are_not_filled_from_other_columns():
    data = ninho()
    data["nutriments"].pop("energy-kcal_serving")
    data["nutriments"].pop("fiber_serving")
    data["nutriments"]["sugars_100g"] = 50
    facts = OpenFoodFactsClient._to_product(data, "12345678").nutrition
    assert facts.basis == "per_serving" and facts.protein_g == 6.3
    assert facts.calories_kcal is None and facts.fiber_g is None and facts.sugars_g is None
    assert "protein_energy_percent" not in assess_goal(facts, "muscle_gain").metrics


def test_missing_or_invalid_serving_column_keeps_reference_unknown():
    data = ninho()
    data["nutriments"] = {"proteins_100g": 25.2, "proteins_serving": -1,
                          "energy-kcal_serving": "NaN", "fiber_serving": None}
    assert OpenFoodFactsClient._to_product(data, "12345678").nutrition.basis == "unknown"


def test_explicit_other_basis_is_not_replaced_by_fallback():
    data = ninho()
    data["nutrition_data_per"] = "100ml"
    facts = OpenFoodFactsClient._to_product(data, "12345678").nutrition
    assert facts.basis == "per_100ml" and facts.protein_g == 25.2


def test_corrected_values_and_basis_invalidate_previous_analysis_key():
    product = OpenFoodFactsClient._to_product(ninho(), "7891000325858")
    old = product.model_copy(update={"nutrition": product.nutrition.model_copy(
        update={"basis": NutritionBasis.UNKNOWN, "protein_g": 25.2, "calories_kcal": 496})})
    uid, profile = uuid4(), UserProfile(goal="muscle_gain")
    def key(p):
        return build_analysis_cache_key(uid, p, profile, provider="gemini", model="m", prompt_version="v")
    assert key(old) != key(product)


def test_ninho_serving_selection_does_not_weaken_confirmed_milk_allergy():
    from app.services.nutrition_service import NutritionService
    product = OpenFoodFactsClient._to_product(ninho(), "7891000325858")
    def forbidden(_):
        pytest.fail("Confirmed allergy must not depend on Gemini")
    result = NutritionService(forbidden).analyze(product, UserProfile(goal="muscle_gain", allergies=["leite"]))
    assert result.status == "not_recommended"
    assert result.conflicts
    assert any("20.32%" in reason for reason in result.reasons)
