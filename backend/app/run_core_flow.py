"""Run the mocked core analysis flow without starting FastAPI."""

import json
from pathlib import Path

from app.models.nutrition import NutritionFacts, Product, ProductSource
from app.models.user import UserProfile
from app.services.nutrition_service import analyze_product


def build_mock_input() -> tuple[Product, UserProfile]:
    product = Product(
        name="Iogurte de morango",
        brand="NutriIA Demo",
        source=ProductSource.LABEL,
        ingredients=[
            "leite reconstituído",
            "açúcar",
            "maltodextrina",
            "suco concentrado de morango",
        ],
        nutrition=NutritionFacts(
            calories_kcal=130,
            sugars_g=18,
            carbohydrates_g=22,
            protein_g=4,
            sodium_mg=80,
        ),
    )
    profile = UserProfile(
        name="Usuário demonstrativo",
        goal="emagrecimento",
        restrictions=["sem lactose", "sem açúcar"],
    )
    return product, profile


def output_path() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts/v0007-core-analysis-flow/result.json"


def main() -> None:
    product, profile = build_mock_input()
    result = analyze_product(product, profile)
    destination = output_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Provider: {result.provider}")
    print(f"Status: {result.status.value}")
    print(f"Resultado salvo em: {destination}")


if __name__ == "__main__":
    main()
