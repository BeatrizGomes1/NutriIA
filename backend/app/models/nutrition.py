from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    RECOMMENDED = "recommended"
    ATTENTION = "attention"
    NOT_RECOMMENDED = "not_recommended"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class ProductSource(StrEnum):
    EAN = "ean"
    LABEL = "label"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class NutritionFacts(BaseModel):
    """Nutrition values available for the product.

    Values are optional because the requirements explicitly allow incomplete
    labels. Negative values, however, are never meaningful here.
    """

    calories_kcal: float | None = Field(default=None, ge=0)
    sugars_g: float | None = Field(default=None, ge=0)
    carbohydrates_g: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)

    def has_any_value(self) -> bool:
        return any(value is not None for value in self.model_dump().values())


class Product(BaseModel):
    name: str | None = None
    brand: str | None = None
    ean: str | None = None
    source: ProductSource = ProductSource.UNKNOWN
    ingredients: list[str] = Field(default_factory=list)
    ingredients_text: str | None = None
    nutrition: NutritionFacts = Field(default_factory=NutritionFacts)

    def has_identity(self) -> bool:
        return bool((self.name and self.name.strip()) or (self.ean and self.ean.strip()))

    def ingredient_text(self) -> str:
        values = [*self.ingredients]
        if self.ingredients_text:
            values.append(self.ingredients_text)
        return ", ".join(value for value in values if value and value.strip())


class Conflict(BaseModel):
    term: str
    category: str
    profile_item: str
    evidence: str


class AnalysisContext(BaseModel):
    """Structured input sent to the AI analysis provider."""

    product: Product
    profile: dict[str, Any]
    normalized_ingredients: str
    conflicts: list[Conflict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)

    def to_provider_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AnalysisResult(BaseModel):
    status: AnalysisStatus
    product_name: str | None = None
    summary: str
    reasons: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    disclaimer: str = "Esta análise é informativa e não substitui orientação profissional."
    provider: str = "mock"
