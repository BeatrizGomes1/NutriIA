"""Read-only client for product lookups in Open Food Facts."""

from typing import Any

import httpx

from app.models.nutrition import NutritionFacts, Product, ProductSource


class OpenFoodFactsError(RuntimeError):
    """Base error for failed Open Food Facts lookups."""


class ProductNotFoundError(OpenFoodFactsError):
    """Raised when Open Food Facts has no product for the requested EAN."""


class OpenFoodFactsClient:
    BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
    USER_AGENT = "NutriIA/0.1 (local development)"
    PRODUCT_FIELDS = "code,product_name,brands,ingredients_text,nutriments"

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

        return Product(
            name=_non_empty_string(data.get("product_name")),
            brand=_non_empty_string(data.get("brands")),
            ean=str(ean),
            source=ProductSource.EAN,
            ingredients_text=_non_empty_string(data.get("ingredients_text")),
            nutrition=NutritionFacts(
                calories_kcal=_number(nutriments.get("energy-kcal_100g")),
                sugars_g=_number(nutriments.get("sugars_100g")),
                carbohydrates_g=_number(nutriments.get("carbohydrates_100g")),
                protein_g=_number(nutriments.get("proteins_100g")),
                sodium_mg=_to_milligrams(nutriments.get("sodium_100g")),
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
    return parsed if parsed >= 0 else None


def _to_milligrams(value: Any) -> float | None:
    sodium_g = _number(value)
    return sodium_g * 1000 if sodium_g is not None else None
