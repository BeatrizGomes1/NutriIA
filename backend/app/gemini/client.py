from google import genai

from app.config.settings import Settings, get_settings


client = None


def _build_client(settings: Settings | None = None):
    settings = settings or get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        return None

    return genai.Client(api_key=api_key)


def generate_response(prompt: str) -> str:
    global client

    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty")

    settings = get_settings()
    if client is None:
        client = _build_client(settings)

    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    try:
        response = client.interactions.create(
            model=settings.gemini_model,
            input=prompt,
        )
    except Exception as error:
        raise RuntimeError("Failed to communicate with Gemini") from error

    response_text = getattr(response, "output_text", None)
    if not response_text:
        raise RuntimeError("Gemini returned an empty response")

    return response_text
