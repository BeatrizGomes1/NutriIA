import httpx
import pytest

from app.models.nutrition import ProductSource
from app.services.open_food_facts import (
    OpenFoodFactsClient,
    OpenFoodFactsError,
    ProductNotFoundError,
)


def _client_for(payload, *, status_code=200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == OpenFoodFactsClient.USER_AGENT
        assert request.url.params["fields"] == OpenFoodFactsClient.PRODUCT_FIELDS
        return httpx.Response(status_code, json=payload)

    return OpenFoodFactsClient(transport=httpx.MockTransport(handler))


def test_get_product_maps_open_food_facts_response():
    client = _client_for(
        {
            "status": 1,
            "code": "3017624010701",
            "product": {
                "product_name": "Nutella",
                "brands": "Ferrero",
                "ingredients_text": "Sugar, palm oil, hazelnuts",
                "nutriments": {
                    "energy-kcal_100g": 539,
                    "sugars_100g": 56.3,
                    "carbohydrates_100g": 57.5,
                    "proteins_100g": 6.3,
                    "sodium_100g": 0.107,
                },
            },
        }
    )

    product = client.get_product("3017624010701")

    assert product.name == "Nutella"
    assert product.brand == "Ferrero"
    assert product.ean == "3017624010701"
    assert product.source == ProductSource.EAN
    assert product.ingredients_text == "Sugar, palm oil, hazelnuts"
    assert product.nutrition.calories_kcal == 539
    assert product.nutrition.sugars_g == 56.3
    assert product.nutrition.carbohydrates_g == 57.5
    assert product.nutrition.protein_g == 6.3
    assert product.nutrition.sodium_mg == 107


def test_get_product_allows_missing_fields():
    client = _client_for({"status": 1, "product": {}})

    product = client.get_product("1234567890123")

    assert product.ean == "1234567890123"
    assert product.name is None
    assert product.nutrition.has_any_value() is False


def test_get_product_raises_for_unknown_ean():
    client = _client_for({"status": 0, "status_verbose": "product not found"})

    with pytest.raises(ProductNotFoundError, match="was not found"):
        client.get_product("0000000000000")


def test_get_product_raises_for_http_error():
    client = _client_for({"error": "unavailable"}, status_code=503)

    with pytest.raises(OpenFoodFactsError, match="lookup failed"):
        client.get_product("3017624010701")


def test_get_product_raises_for_invalid_json():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = OpenFoodFactsClient(transport=httpx.MockTransport(handler))

    with pytest.raises(OpenFoodFactsError, match="lookup failed"):
        client.get_product("3017624010701")


def test_get_product_rejects_empty_ean():
    with pytest.raises(ValueError, match="EAN must not be empty"):
        OpenFoodFactsClient().get_product("  ")
