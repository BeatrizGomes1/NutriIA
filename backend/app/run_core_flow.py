"""Run the core analysis flow with a real OFF lookup and mocked analysis."""

import json
from pathlib import Path

from app.models.user import UserProfile
from app.services.open_food_facts import OpenFoodFactsClient
from app.services.nutrition_service import analyze_product

DEMO_EAN = "3017624010701"

def build_mock_profile() -> UserProfile:
    profile = UserProfile(
        name="Usuário demonstrativo",
        goal="emagrecimento",
        restrictions=["sugar"],
    )
    return profile


def output_path() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts/v0007-core-analysis-flow/result.json"


def main() -> None:
    product = OpenFoodFactsClient().get_product(DEMO_EAN)
    profile = build_mock_profile()
    result = analyze_product(product, profile)
    destination = output_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Provider: {result.provider}")
    print(f"Produto: {product.name or product.ean}")
    print(f"Status: {result.status.value}")
    print(f"Resultado salvo em: {destination}")


if __name__ == "__main__":
    main()
