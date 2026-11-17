from enum import StrEnum
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NutritionBasis(StrEnum):
    PER_100G = "per_100g"
    PER_100ML = "per_100ml"
    PER_SERVING = "per_serving"
    UNKNOWN = "unknown"


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

    model_config = ConfigDict(allow_inf_nan=False)

    basis: NutritionBasis = NutritionBasis.UNKNOWN
    serving_quantity: float | None = Field(default=None, gt=0)
    serving_unit: Literal["g", "ml"] | None = None

    @model_validator(mode="after")
    def validate_serving(self):
        if (self.serving_quantity is None) != (self.serving_unit is None):
            raise ValueError("serving_quantity and serving_unit must be supplied together")
        return self

    calories_kcal: float | None = Field(default=None, ge=0, strict=True)
    sugars_g: float | None = Field(default=None, ge=0, strict=True)
    carbohydrates_g: float | None = Field(default=None, ge=0, strict=True)
    protein_g: float | None = Field(default=None, ge=0, strict=True)
    fiber_g: float | None = Field(default=None, ge=0, strict=True)
    sodium_mg: float | None = Field(default=None, ge=0, strict=True)

    def has_any_value(self) -> bool:
        return any(getattr(self, field) is not None for field in (
            "calories_kcal", "sugars_g", "carbohydrates_g", "protein_g", "fiber_g", "sodium_mg"
        ))


class FoodSafetyData(BaseModel):
    """Source declarations, never inferred from a product name or nutrient table."""

    ingredients_status: Literal["unknown", "complete", "incomplete", "unreadable"] = "unknown"
    allergen_statement: str | None = None
    cross_contact_statement: str | None = None
    ingredient_source_text: str | None = None


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
    food_safety: FoodSafetyData = Field(default_factory=FoodSafetyData)

    @model_validator(mode="after")
    def validate_ingredient_quality(self):
        from app.utils.ingredient_quality import separate_ingredients

        raw = self.ingredients_text or ", ".join(self.ingredients)
        clean, contaminated = separate_ingredients(raw)
        if contaminated:
            self.food_safety.ingredient_source_text = self.food_safety.ingredient_source_text or raw
            if self.food_safety.ingredients_status != "unreadable":
                self.food_safety.ingredients_status = "incomplete"
            self.ingredients_text = clean or None
            self.ingredients = [part.strip() for part in clean.split(",") if part.strip()]
        return self

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
