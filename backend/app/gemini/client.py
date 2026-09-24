import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

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


def generate_response(prompt: str) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty")

    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
    except Exception as error:
        raise RuntimeError("Failed to communicate with Gemini") from error

    response_text = getattr(response, "text", None)
    if not response_text:
        raise RuntimeError("Gemini returned an empty response")

    return response_text
