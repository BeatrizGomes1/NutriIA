from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.nutrition import AnalysisResult, Product
from app.models.user import UserProfile


Objective = Literal["weight_loss", "muscle_gain"]
CaptureStatus = Literal["found", "not_found", "insufficient"]


class ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_or_nickname: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    age_range: str | None = Field(default=None, max_length=40)
    objective: Objective
    declared_allergies: list[str] = Field(default_factory=list)
    avoided_ingredients: list[str] = Field(default_factory=list)
    food_preferences: list[str] = Field(default_factory=list)
    onboarding_completed: bool = False

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        local_part, separator, domain = value.partition("@")
        if not separator or not local_part or "." not in domain or " " in value:
            raise ValueError("email must be a valid email address")
        return value.lower()

    @field_validator(
        "declared_allergies",
        "avoided_ingredients",
        "food_preferences",
    )
    @classmethod
    def validate_terms(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("profile terms must not be empty")
        return normalized

    def to_domain(self) -> UserProfile:
        return UserProfile(
            name=self.name_or_nickname,
            email=self.email,
            age_range=self.age_range,
            goal=self.objective,
            allergies=self.declared_allergies,
            restrictions=self.avoided_ingredients,
            preferences=self.food_preferences,
            onboarding_completed=self.onboarding_completed,
        )


class ProfileResponse(BaseModel):
    id: UUID
    name_or_nickname: str
    email: str
    age_range: str | None
    objective: Objective
    declared_allergies: list[str]
    avoided_ingredients: list[str]
    food_preferences: list[str]
    onboarding_completed: bool

    @classmethod
    def from_domain(cls, profile: UserProfile) -> "ProfileResponse":
        return cls(
            id=profile.id,
            name_or_nickname=profile.name,
            email=profile.email,
            age_range=profile.age_range,
            objective=profile.goal,
            declared_allergies=profile.allergies,
            avoided_ingredients=profile.restrictions,
            food_preferences=profile.preferences,
            onboarding_completed=profile.onboarding_completed,
        )


class EanCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ean: str = Field(min_length=8, max_length=32, pattern=r"^[0-9]+$")


class CaptureAnalysisResponse(BaseModel):
    capture_id: UUID
    source_status: CaptureStatus
    product: Product | None
    analysis: AnalysisResult | None


class CaptureHistoryResponse(BaseModel):
    capture_id: UUID
    captured_at: datetime
    ean: str | None
    source_status: CaptureStatus
    product: Product | None
    analysis: AnalysisResult | None
