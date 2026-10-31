from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_history_service, get_profile_service, get_workflow_service
from app.api.schemas import ProfilePayload
from app.config.settings import Settings
from app.main import create_app
from app.services.nutrition_workflow_service import CaptureAnalysisOutcome


@pytest.fixture
def api_client():
    application = create_app(
        Settings(_env_file=None, api_v1_prefix="/api/v1", cors_origins="")
    )
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()


def test_health_route(api_client):
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_profile_route(api_client):
    profile_id = uuid4()

    class FakeProfileService:
        def create(self, profile):
            return profile.model_copy(update={"id": str(profile_id)})

    api_client.app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()

    response = api_client.post(
        "/api/v1/profiles",
        json={
            "name_or_nickname": "Ana",
            "email": "ANA@example.com",
            "objective": "weight_loss",
            "declared_allergies": ["amendoim"],
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(profile_id)
    assert response.json()["email"] == "ana@example.com"
    assert response.json()["declared_allergies"] == ["amendoim"]


def test_invalid_profile_payload_is_rejected(api_client):
    response = api_client.post(
        "/api/v1/profiles",
        json={
            "name_or_nickname": "Ana",
            "email": "not-an-email",
            "objective": "weight_loss",
        },
    )

    assert response.status_code == 422


def test_missing_profile_returns_not_found(api_client):
    class FakeProfileService:
        def get(self, _user_id):
            return None

    api_client.app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()

    response = api_client.get(f"/api/v1/profiles/{uuid4()}")

    assert response.status_code == 404


def test_ean_capture_route_returns_capture_and_analysis_fields(api_client):
    capture_id = uuid4()
    user_id = uuid4()

    class FakeWorkflowService:
        def capture_ean(self, requested_user_id, ean):
            assert requested_user_id == user_id
            assert ean == "3017624010701"
            return CaptureAnalysisOutcome(
                capture_id=str(capture_id),
                source_status="not_found",
                product=None,
                analysis=None,
            )

    api_client.app.dependency_overrides[get_workflow_service] = lambda: FakeWorkflowService()

    response = api_client.post(
        f"/api/v1/profiles/{user_id}/captures/ean",
        json={"ean": "3017624010701"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "capture_id": str(capture_id),
        "source_status": "not_found",
        "product": None,
        "analysis": None,
    }


def test_gemini_failure_returns_gateway_error_without_internal_details(api_client):
    user_id = uuid4()

    class FakeWorkflowService:
        def capture_ean(self, _requested_user_id, _ean):
            raise RuntimeError("provider failure containing internal details")

    api_client.app.dependency_overrides[get_workflow_service] = lambda: FakeWorkflowService()

    response = api_client.post(
        f"/api/v1/profiles/{user_id}/captures/ean",
        json={"ean": "3017624010701"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Analysis provider failed"}


def test_history_route_uses_pagination(api_client):
    user_id = uuid4()

    class FakeHistoryService:
        def list(self, requested_user_id, *, limit, offset):
            assert requested_user_id == user_id
            assert limit == 5
            assert offset == 10
            return []

    api_client.app.dependency_overrides[get_history_service] = lambda: FakeHistoryService()

    response = api_client.get(
        f"/api/v1/profiles/{user_id}/history/analyses?limit=5&offset=10"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_profile_payload_maps_api_names_to_domain_names():
    profile = ProfilePayload(
        name_or_nickname="Ana",
        email="ana@example.com",
        objective="muscle_gain",
        declared_allergies=["leite"],
        avoided_ingredients=["açúcar"],
        food_preferences=["vegetariano"],
    ).to_domain()

    assert profile.name == "Ana"
    assert profile.goal == "muscle_gain"
    assert profile.allergies == ["leite"]
    assert profile.restrictions == ["açúcar"]
    assert profile.preferences == ["vegetariano"]
