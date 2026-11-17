"""Nutrition reference regression tests; no external services or database."""
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.gemini import nutrition_ai
from app.models.nutrition import AnalysisContext, NutritionFacts, Product
from app.models.user import UserProfile
from app.services.database_service import product_to_domain, product_values
from app.services.nutrition_workflow_service import build_analysis_cache_key
from app.services.open_food_facts import OpenFoodFactsClient


def restore(product):
    return product_to_domain(SimpleNamespace(id=uuid4(), **product_values(product)))


@pytest.mark.parametrize("basis,quantity,unit", [
    ("per_100g", None, None), ("per_100ml", None, None),
    ("per_serving", 30, "g"), ("per_serving", 200, "ml"),
    ("per_serving", None, None), ("unknown", None, None),
])
def test_photo_extraction_persistence_and_provider_preserve_reference(monkeypatch, basis, quantity, unit):
    payload = {"name": "Product", "ingredients_text": "water",
               "nutrition": {"basis": basis, "serving_quantity": quantity,
                             "serving_unit": unit, "calories_kcal": 42, "sugars_g": 0}}
    monkeypatch.setattr(nutrition_ai, "generate_image_response", lambda *_: json.dumps(payload))
    extracted = nutrition_ai.extract_product_from_label(b"image", "image/png")
    saved = restore(extracted)
    assert saved.nutrition == extracted.nutrition
    context = AnalysisContext(product=saved, profile={}).to_provider_payload()
    assert context["product"]["nutrition"]["basis"] == basis
    assert saved.nutrition.calories_kcal == 42
    assert saved.nutrition.sugars_g == 0
    assert saved.nutrition.protein_g is None
    assert saved.nutrition.serving_quantity == quantity
    assert saved.nutrition.serving_unit == unit


def test_missing_basis_is_not_inferred_from_serving_text():
    saved = restore(Product(serving_information={"serving_size": "100 g"},
                            nutrition={"protein_g": 3}))
    assert saved.nutrition.basis == "unknown"
    assert saved.nutrition.protein_g == 3


@pytest.mark.parametrize("table", [
    {"basis": "per_100g", "per_100g": {"protein_g": 5}},
    {"protein_g": 5},
])
def test_legacy_numbers_are_preserved_but_basis_is_untrusted(table):
    row = SimpleNamespace(id=uuid4(), ean="12345678", name=None, brand=None,
                          ingredients_raw=None, ingredients_normalized=[],
                          serving_information=None, nutrition_table=table)
    assert product_to_domain(row).nutrition.basis == "unknown"
    assert product_to_domain(row).nutrition.protein_g == 5
    assert row.nutrition_table == table


@pytest.mark.parametrize("data", [
    {"basis": "invalid"}, {"serving_quantity": 30}, {"serving_unit": "g"},
    {"serving_quantity": 0, "serving_unit": "g"},
    {"serving_quantity": 1, "serving_unit": "oz"},
    {"protein_g": float("inf")}, {"sugars_g": float("nan")},
    {"calories_kcal": -1},
])
def test_invalid_reference_or_values_are_rejected(data):
    with pytest.raises(ValidationError):
        NutritionFacts(**data)


def test_metadata_is_not_a_nutrient():
    assert not NutritionFacts(basis="per_serving", serving_quantity=30, serving_unit="g").has_any_value()
    assert NutritionFacts(sugars_g=0).has_any_value()


@pytest.mark.parametrize("declared,suffix,basis", [
    ("100g", "100g", "unknown"), (None, "100g", "unknown"),
    ("100ml", "100g", "per_100ml"), ("serving", "serving", "per_serving"),
])
def test_off_preserves_selected_column_without_mixing_or_conversion(declared, suffix, basis):
    data = {"nutrition_data_per": declared, "serving_size": "200 ml",
            "nutriments": {f"energy-kcal_{suffix}": 42, f"sodium_{suffix}": .1}}
    if suffix == "serving":
        data["nutriments"]["sugars_100g"] = 12
    client = OpenFoodFactsClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"status": 1, "product": data})))
    saved = restore(client.get_product("12345678"))
    assert saved.nutrition.basis == basis
    assert saved.nutrition.calories_kcal == 42
    assert saved.nutrition.sodium_mg == 100
    assert saved.nutrition.sugars_g is None
    assert saved.nutrition.serving_quantity == 200
    assert saved.nutrition.serving_unit == "ml"


def test_off_does_not_use_packaging_to_infer_basis_or_units():
    product = OpenFoodFactsClient._to_product({"quantity": "1 l", "serving_quantity": 200,
        "nutriments": {"proteins_100g": 2, "sugars_100g": "Infinity"}}, "12345678")
    assert product.nutrition.basis == "unknown"
    assert product.nutrition.serving_quantity is None
    assert product.nutrition.sugars_g is None


def test_cache_changes_with_basis_and_serving_size():
    uid = uuid4()
    def key(nutrition):
        return build_analysis_cache_key(uid, Product(nutrition=nutrition), UserProfile(),
                                        provider="mock", model="m", prompt_version="v")
    assert key({"protein_g": 2}) != key({"protein_g": 2, "basis": "per_100g"})
    assert key({"basis": "per_serving", "serving_quantity": 30, "serving_unit": "g"}) != key(
        {"basis": "per_serving", "serving_quantity": 60, "serving_unit": "g"})


@pytest.mark.parametrize("text,quantity,unit", [
    ("1 cup (200 ml)", 200, "ml"), ("1 bar (30,5 g)", 30.5, "g"),
    ("30 g / 100 ml", None, None), ("1 cup", None, None),
])
def test_off_serving_text_requires_one_unambiguous_mass_or_volume(text, quantity, unit):
    product = OpenFoodFactsClient._to_product({"serving_size": text}, "12345678")
    assert product.nutrition.serving_quantity == quantity
    assert product.nutrition.serving_unit == unit


def test_absent_nutrition_does_not_replace_existing_table_on_off_upsert():
    assert product_values(Product())["nutrition_table"] is None
