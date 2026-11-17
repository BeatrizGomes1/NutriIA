"""Cliente somente leitura para consultar produtos no Open Food Facts."""

import math
import re
from typing import Any

import httpx

from app.models.nutrition import NutritionBasis, NutritionFacts, Product, ProductSource


class OpenFoodFactsError(RuntimeError):
    """Erro base para falhas nas consultas ao Open Food Facts."""


class ProductNotFoundError(OpenFoodFactsError):
    """Erro lançado quando o Open Food Facts não encontra o EAN consultado."""


class OpenFoodFactsClient:
    BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
    USER_AGENT = "NutriIA/0.1 (local development)"
    PRODUCT_FIELDS = "code,product_name,brands,ingredients_text,nutriments,quantity,serving_size,serving_quantity,nutrition_data_per,allergens,traces"

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.transport = transport

    def get_product(self, ean: str) -> Product:
        if not ean or not ean.strip():
            raise ValueError("EAN must not be empty")

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                headers={"User-Agent": self.USER_AGENT},
            ) as client:
                response = client.get(
                    f"{self.BASE_URL}/{ean.strip()}.json",
                    params={"fields": self.PRODUCT_FIELDS},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OpenFoodFactsError(f"Open Food Facts lookup failed for EAN {ean!r}") from error

        if not isinstance(payload, dict):
            raise OpenFoodFactsError("Open Food Facts returned an invalid response")
        if payload.get("status") != 1:
            raise ProductNotFoundError(f"Product with EAN {ean!r} was not found in Open Food Facts")

        product_data = payload.get("product")
        if not isinstance(product_data, dict):
            raise OpenFoodFactsError("Open Food Facts response has no valid product object")

        return self._to_product(product_data, payload.get("code") or ean)

    @classmethod
    def _to_product(cls, data: dict[str, Any], ean: str) -> Product:
        nutriments = data.get("nutriments")
        if not isinstance(nutriments, dict):
            nutriments = {}

        declared_basis = data.get("nutrition_data_per")
        # OFF's _100g suffix can mean either 100 g or 100 ml. Do not guess
        # from packaging quantity, category or serving size.
        basis = NutritionBasis.UNKNOWN
        suffix = "100g"
        if declared_basis == "serving":
            basis, suffix = NutritionBasis.PER_SERVING, "serving"
        elif declared_basis == "100ml":
            basis = NutritionBasis.PER_100ML
        serving = _serving_reference(data.get("serving_size"))
        # Prefer an explicitly available serving column over an ambiguous
        # mass/volume reference. Read every nutrient from this one column.
        if basis == NutritionBasis.UNKNOWN and serving and any(
            _number(nutriments.get(f"{name}_serving")) is not None
            for name in ("energy-kcal", "proteins", "fiber", "sugars", "carbohydrates", "sodium")
        ):
            basis, suffix = NutritionBasis.PER_SERVING, "serving"

        return Product(
            name=_non_empty_string(data.get("product_name")),
            brand=_non_empty_string(data.get("brands")),
            ean=str(ean),
            source=ProductSource.EAN,
            ingredients_text=_non_empty_string(data.get("ingredients_text")),
            food_safety={
                "allergen_statement": _non_empty_string(data.get("allergens")),
                "cross_contact_statement": _non_empty_string(data.get("traces")),
            },
            serving_information={
                key: data[key]
                for key in ("quantity", "serving_size", "serving_quantity", "nutrition_data_per")
                if data.get(key) is not None
            } or None,
            nutrition=NutritionFacts(
                basis=basis,
                **serving,
                calories_kcal=_number(nutriments.get(f"energy-kcal_{suffix}")),
                sugars_g=_number(nutriments.get(f"sugars_{suffix}")),
                carbohydrates_g=_number(nutriments.get(f"carbohydrates_{suffix}")),
                fiber_g=_number(nutriments.get(f"fiber_{suffix}")),
                protein_g=_number(nutriments.get(f"proteins_{suffix}")),
                sodium_mg=_to_milligrams(nutriments.get(f"sodium_{suffix}")),
            ),
        )


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _to_milligrams(value: Any) -> float | None:
    sodium_g = _number(value)
    return sodium_g * 1000 if sodium_g is not None else None


def _serving_reference(value: Any) -> dict[str, Any]:
    """Accept an explicit mass/volume, never infer units from a bare number."""
    if not isinstance(value, str):
        return {}
    if re.search(r"[-\u2212]\s*\d", value):
        return {}
    matches = re.findall(r"(?<![\w.,+\-])(\d+(?:[.,]\d+)?)\s*(g|ml)\b", value, re.IGNORECASE)
    if len(matches) != 1:
        return {}
    quantity_text, unit = matches[0]
    quantity = _number(quantity_text.replace(",", "."))
    return {"serving_quantity": quantity, "serving_unit": unit.lower()} if quantity else {}
