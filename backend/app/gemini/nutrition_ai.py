import json

from .client import generate_response
from .prompts import NUTRITION_PLAN_PROMPT, PRODUCT_ANALYSIS_PROMPT


def generate_nutrition_plan(data):
    prompt = NUTRITION_PLAN_PROMPT.format(data=data)
    return generate_response(prompt)


def generate_product_analysis(context: dict) -> str:
    """Send a structured product-analysis context to Gemini."""

    data = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = PRODUCT_ANALYSIS_PROMPT.format(data=data)
    return generate_response(prompt)
