from enum import StrEnum
from datetime import datetime
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
    """Valores nutricionais disponíveis para o produto.

    Os valores são opcionais porque os requisitos permitem rótulos
    incompletos. Valores negativos, porém, não são válidos neste contexto.
    """

    calories_kcal: float | None = Field(default=None, ge=0)
    sugars_g: float | None = Field(default=None, ge=0)
    carbohydrates_g: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    sodium_mg: float | None = Field(default=None, ge=0)

    def has_any_value(self) -> bool:
        return any(value is not None for value in self.model_dump().values())


class Product(BaseModel):
    id: str | None = None
    name: str | None = None
    brand: str | None = None
    ean: str | None = None
    source: ProductSource = ProductSource.UNKNOWN
    ingredients: list[str] = Field(default_factory=list)
    ingredients_text: str | None = None
    serving_information: dict[str, Any] | None = None
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
    evidence: str = Field(description="Explicação legível de como o ingrediente se relaciona ao perfil.")
    source_excerpt: str = Field(description="Trecho literal dos ingredientes que sustenta o conflito.")


class AnalysisContext(BaseModel):
    """Entrada estruturada enviada ao provedor de análise por IA."""

    product: Product
    profile: dict[str, Any]
    blocking_reasons: list[str] = Field(default_factory=list)

    def to_provider_payload(self) -> dict[str, Any]:
        product = self.product.model_dump(mode="json")
        product.pop("id", None)
        profile = {
            key: self.profile.get(key)
            for key in ("goal", "allergies", "restrictions", "preferences")
        }
        return {
            "product": product,
            "profile": profile,
            "blocking_reasons": self.blocking_reasons,
        }


class AnalysisResult(BaseModel):
    id: str | None = None
    created_at: datetime | None = None
    status: AnalysisStatus
    product_name: str | None = None
    summary: str
    reasons: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    disclaimer: str = "Esta análise é informativa e não substitui orientação profissional."
    provider: str = "mock"
