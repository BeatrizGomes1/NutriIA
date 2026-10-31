from types import SimpleNamespace

import pytest

from app.config.settings import Settings
from app.gemini import client as gemini_client


def test_default_settings_use_available_gemini_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    assert Settings(_env_file=None).gemini_model == "gemini-3.6-flash"


def test_generate_response_uses_model_and_content(monkeypatch):
    class FakeResponse:
        output_text = "Resposta simulada"

    class FakeInteractions:
        def create(self, *, model, input):
            assert model == "gemini-3.6-flash"
            assert input == "prompt de teste"
            return FakeResponse()

    class FakeClient:
        interactions = FakeInteractions()

    monkeypatch.setattr(gemini_client, "client", FakeClient())
    monkeypatch.setattr(
        gemini_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None, gemini_model="gemini-3.6-flash"),
    )

    assert gemini_client.generate_response("prompt de teste") == "Resposta simulada"


def test_generate_response_without_client_raises_configuration_error(monkeypatch):
    monkeypatch.setattr(gemini_client, "client", None)
    monkeypatch.setattr(
        gemini_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None, gemini_model="gemini-3.6-flash"),
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
        gemini_client.generate_response("qualquer prompt")


def test_generate_response_rejects_empty_prompt():
    with pytest.raises(ValueError, match="Prompt must not be empty"):
        gemini_client.generate_response("  ")


def test_generate_response_rejects_empty_response(monkeypatch):
    class FakeResponse:
        output_text = ""

    class FakeInteractions:
        def create(self, *, model, input):
            return FakeResponse()

    class FakeClient:
        interactions = FakeInteractions()

    monkeypatch.setattr(gemini_client, "client", FakeClient())
    monkeypatch.setattr(
        gemini_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None, gemini_model="gemini-3.6-flash"),
    )

    with pytest.raises(RuntimeError, match="Gemini returned an empty response"):
        gemini_client.generate_response("prompt de teste")


def test_generate_response_wraps_interactions_api_errors(monkeypatch):
    class FakeInteractions:
        def create(self, *, model, input):
            raise OSError("network unavailable")

    class FakeClient:
        interactions = FakeInteractions()

    monkeypatch.setattr(gemini_client, "client", FakeClient())
    monkeypatch.setattr(
        gemini_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None, gemini_model="gemini-3.6-flash"),
    )

    with pytest.raises(RuntimeError, match="Failed to communicate with Gemini") as error:
        gemini_client.generate_response("prompt de teste")

    assert isinstance(error.value.__cause__, OSError)
