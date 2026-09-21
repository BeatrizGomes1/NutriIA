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


def test_generate_response_without_client_returns_fallback_message(monkeypatch):
    monkeypatch.setattr(gemini_client, "client", None)

    assert gemini_client.generate_response("qualquer prompt") == "Gemini client unavailable"
