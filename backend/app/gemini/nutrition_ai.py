import json

from pydantic import ValidationError

from app.models.nutrition import Product, ProductSource

from .client import generate_image_response, generate_response
from .prompts import LABEL_EXTRACTION_PROMPT, NUTRITION_PLAN_PROMPT, PRODUCT_ANALYSIS_PROMPT


def generate_nutrition_plan(data):
    prompt = NUTRITION_PLAN_PROMPT.format(data=data)
    return generate_response(prompt)


def generate_product_analysis(context: dict) -> str:
    """Envia ao Gemini o contexto estruturado da análise do produto."""

    data = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = PRODUCT_ANALYSIS_PROMPT.format(data=data)
    return generate_response(prompt)


def extract_product_from_label(image_data: bytes, mime_type: str) -> Product:
    response_text = generate_image_response(
        LABEL_EXTRACTION_PROMPT,
        image_data,
        mime_type,
    )
    try:
        payload = json.loads(response_text)
        product = Product.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as error:
        raise RuntimeError("Gemini returned invalid label data") from error

    product.source = ProductSource.LABEL
    return product
