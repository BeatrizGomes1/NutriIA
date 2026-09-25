import pytest

from app.gemini import client as gemini_client


def test_generate_response_uses_model_and_content(monkeypatch):
    class FakeResponse:
        text = "Resposta simulada"

    class FakeModels:
        def generate_content(self, *, model, contents):
            assert model == "gemini-2.0-flash"
            assert contents == "prompt de teste"
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(gemini_client, "client", FakeClient())

    assert gemini_client.generate_response("prompt de teste") == "Resposta simulada"


def test_generate_response_without_client_raises_configuration_error(monkeypatch):
    monkeypatch.setattr(gemini_client, "client", None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not configured"):
        gemini_client.generate_response("qualquer prompt")


def test_generate_response_rejects_empty_prompt():
    with pytest.raises(ValueError, match="Prompt must not be empty"):
        gemini_client.generate_response("  ")


def test_generate_response_rejects_empty_response(monkeypatch):
    class FakeResponse:
        text = ""

    class FakeModels:
        def generate_content(self, *, model, contents):
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(gemini_client, "client", FakeClient())

    with pytest.raises(RuntimeError, match="Gemini returned an empty response"):
        gemini_client.generate_response("prompt de teste")
