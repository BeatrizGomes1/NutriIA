from app.gemini.nutrition_ai import generate_nutrition_plan


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
