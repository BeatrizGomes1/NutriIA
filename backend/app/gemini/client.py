import os

from google import genai


MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _build_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


client = _build_client()


def generate_response(prompt):
    if client is None:
        return "Gemini client unavailable"

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return getattr(response, "text", str(response))
    except Exception:
        return "Gemini client unavailable"
