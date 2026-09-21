from .client import generate_response
from .prompts import NUTRITION_PLAN_PROMPT


def generate_nutrition_plan(data):
    prompt = NUTRITION_PLAN_PROMPT.format(data=data)
    return generate_response(prompt)
