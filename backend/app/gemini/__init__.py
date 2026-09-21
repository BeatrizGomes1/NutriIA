"""Gemini integration layer for NutriIA."""

from .client import generate_response
from .nutrition_ai import generate_nutrition_plan

__all__ = ["generate_response", "generate_nutrition_plan"]
