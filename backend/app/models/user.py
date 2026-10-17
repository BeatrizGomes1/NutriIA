from enum import StrEnum

from pydantic import BaseModel, Field


class DietaryGoal(StrEnum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    UNSPECIFIED = "unspecified"


class UserProfile(BaseModel):
    """User-provided context, not a clinical diagnosis."""

    name: str | None = None
    goal: DietaryGoal | str | None = None
    allergies: list[str] = Field(default_factory=list)
    restrictions: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)

    def declared_items(self) -> list[tuple[str, str]]:
        return [
            ("allergy", item)
            for item in self.allergies
            if item and item.strip()
        ] + [
            ("restriction", item)
            for item in self.restrictions
            if item and item.strip()
        ] + [
            ("preference", item)
            for item in self.preferences
            if item and item.strip()
        ]
