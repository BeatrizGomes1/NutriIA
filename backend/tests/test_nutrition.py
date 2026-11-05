import json

import pytest

from app.gemini import nutrition_ai
from app.gemini.nutrition_ai import generate_nutrition_plan
from app.models.nutrition import ProductSource


def test_generate_nutrition_plan_formats_prompt(monkeypatch):
    captured = {}

    def fake_generate_response(prompt):
        captured["prompt"] = prompt
        return "Plano gerado"

    monkeypatch.setattr("app.gemini.nutrition_ai.generate_response", fake_generate_response)

    data = {
        "goal": "emagrecimento",
        "daily_kcal": 1800,
        "restrictions": ["sem glúten"]
    }

    result = generate_nutrition_plan(data)

    assert result == "Plano gerado"
    assert "emagrecimento" in captured["prompt"]
    assert "1800" in captured["prompt"]
    assert "sem glúten" in captured["prompt"]


def test_generate_product_analysis_serializes_context(monkeypatch):
    captured = {}

    def fake_generate_response(prompt):
        captured["prompt"] = prompt
        return '{"status":"recommended"}'

    monkeypatch.setattr(nutrition_ai, "generate_response", fake_generate_response)

    result = nutrition_ai.generate_product_analysis({"product": {"name": "Produto"}})

    assert result == '{"status":"recommended"}'
    assert json.dumps({"product": {"name": "Produto"}}, ensure_ascii=False, indent=2) in captured["prompt"]


def test_extract_product_from_label_parses_structured_response(monkeypatch):
    captured = {}

    def fake_generate_image_response(prompt, image_data, mime_type):
        captured.update(prompt=prompt, image_data=image_data, mime_type=mime_type)
        return json.dumps({
            "name": "Produto",
            "brand": "Marca",
            "ingredients_text": "Sugar, skimmed milk powder",
            "serving_information": {"serving_size": "100 g"},
            "nutrition": {"sugars_g": 55, "protein_g": 6},
        })

    monkeypatch.setattr(nutrition_ai, "generate_image_response", fake_generate_image_response)

    product = nutrition_ai.extract_product_from_label(b"image-data", "image/jpeg")

    assert captured["image_data"] == b"image-data"
    assert captured["mime_type"] == "image/jpeg"
    assert product.name == "Produto"
    assert product.ingredients_text == "Sugar, skimmed milk powder"
    assert product.nutrition.sugars_g == 55
    assert product.source == ProductSource.LABEL


def test_extract_product_from_label_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(nutrition_ai, "generate_image_response", lambda *_args: "not-json")

    with pytest.raises(RuntimeError, match="Gemini returned invalid label data"):
        nutrition_ai.extract_product_from_label(b"image-data", "image/jpeg")
