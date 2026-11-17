"""Source cleanup cannot erase safety evidence or invent nutritional values."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.gemini import nutrition_ai
from app.models.nutrition import AnalysisContext, Product
from app.models.user import UserProfile
from app.services.database_service import product_to_domain, product_values
from app.services.food_safety import assess_food_safety
from app.services.nutrition_service import NutritionService
from app.services.nutrition_observations import observation_catalog
from app.services.open_food_facts import OpenFoodFactsClient


MIXED = ("100 g 74 g %VD INFORMAÇÃO NUTRICIONAL Valor energético (kcal) 333 "
         "Carboidratos (g) 41. Ingredientes do macarrão: farinha de trigo, sal. "
         "ALÉRGICOS: CONTÉM LEITE. PODE CONTER SOJA.")


def test_off_separates_table_and_marks_partial_without_touching_nutrients():
    product = OpenFoodFactsClient._to_product({"ingredients_text": MIXED,
        "allergens": "milk", "serving_size": "74 g", "nutrition_data_per": "serving",
        "nutriments": {"proteins_serving": 6.22}}, "7891079011805")
    assert product.ingredients_text.startswith("farinha de trigo")
    assert "kcal" not in product.ingredients_text
    assert product.food_safety.ingredients_status == "incomplete"
    assert product.food_safety.ingredient_source_text == MIXED
    assert product.nutrition.protein_g == 6.22
    assert product.nutrition.calories_kcal is None


def test_photo_uses_same_quality_check(monkeypatch):
    monkeypatch.setattr(nutrition_ai, "generate_image_response", lambda *args: json.dumps({
        "name": "Miojo", "ingredients_text": MIXED,
        "food_safety": {"ingredients_status": "complete"}}))
    product = nutrition_ai.extract_product_from_label(b"fake", "image/jpeg")
    assert product.source == "label"
    assert product.food_safety.ingredients_status == "incomplete"
    assert "kcal" not in product.ingredients_text


@pytest.mark.parametrize("allergy", ["leite", "trigo"])
def test_original_evidence_survives_even_when_heading_is_damaged(allergy):
    raw = MIXED.replace("Ingredientes do macarrão:", "entes do macarrão:")
    product = Product(name="Miojo", ingredients_text=raw)
    assert not product.ingredients_text and not product.ingredients
    result = NutritionService(lambda _: pytest.fail("No provider needed")).analyze(
        product, UserProfile(allergies=[allergy]))
    assert result.status == "not_recommended"
    assert result.conflicts
    assert any(c.source_excerpt in raw for c in result.conflicts)
    assert any("incompleta" in reason for reason in result.reasons)


def test_cross_contact_still_separate_from_confirmed_conflict():
    product = Product(name="Miojo", ingredients_text=MIXED)
    safety = assess_food_safety(product, {"allergies": ["leite", "soja"]})
    assert {c.profile_item for c in safety.conflicts} == {"leite"}
    assert {c.profile_item for c in safety.cross_contact} == {"soja"}


@pytest.mark.parametrize("raw", ["proteína de soja, fibras vegetais, sal", "Leite integral, minerais", "farinha de trigo, sódio"])
def test_real_ingredients_are_not_removed_by_lone_nutrient_names(raw):
    product = Product(ingredients_text=raw)
    assert product.ingredients_text == raw
    assert product.food_safety.ingredient_source_text is None


def test_quality_and_original_roundtrip_existing_jsonb_without_migration():
    product = Product(name="Miojo", ingredients_text=MIXED)
    restored = product_to_domain(SimpleNamespace(id=uuid4(), **product_values(product)))
    assert restored.food_safety == product.food_safety
    assert restored.ingredients_text == product.ingredients_text


def test_legacy_contaminated_record_is_validated_without_writing():
    record = SimpleNamespace(id=uuid4(), ean="7891079011805", name="Miojo", brand=None,
        ingredients_raw=MIXED, ingredients_normalized=[MIXED.lower()], serving_information=None,
        nutrition_table={"schema_version": 2, "values": {}})
    product = product_to_domain(record)
    assert product.food_safety.ingredients_status == "incomplete"
    assert record.ingredients_raw == MIXED
    assert "kcal" not in product.ingredients_text


def test_ambiguous_source_without_conflict_does_not_declare_safe():
    product = Product(name="Miojo", ingredients_text="Valor energético (kcal) 333 Carboidratos (g) 41")
    result = NutritionService(lambda _: pytest.fail("No provider needed")).analyze(product, UserProfile())
    assert result.status == "insufficient_information"
    assert not result.conflicts
    assert not product.nutrition.has_any_value()


@pytest.mark.parametrize("field,item", [("preferences", "Sem lactose"), ("restrictions", "Lactose"),
                                       ("restrictions", "Intolerância à lactose")])
def test_lactose_uncertainty_is_explained_without_confirmed_conflict(field, item):
    product = Product(name="Ninho", ingredients_text="Leite integral, lactase",
                      nutrition={"basis": "per_serving", "serving_quantity": 25,
                                 "serving_unit": "g", "protein_g": 6.3, "calories_kcal": 124})
    profile = {"goal": "muscle_gain", field: [item]}
    safety = assess_food_safety(product, profile)
    assert not safety.conflicts
    texts = " ".join(o["text"] for o in observation_catalog(AnalysisContext(product=product, profile=profile)).values())
    assert "lactase, sozinha" in texts
    assert "20.32%" in texts
    assert "contém lactose" not in texts.lower()
