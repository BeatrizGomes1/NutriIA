from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import (
    get_auth_service,
    get_current_profile,
    get_history_service,
    get_profile_service,
    get_password_reset_email_service,
    get_workflow_service,
)
from app.api.schemas import ProfilePayload
from app.config.settings import Settings
from app.main import create_app
from app.models.nutrition import Product, ProductSource
from app.models.user import UserProfile
from app.services.nutrition_workflow_service import CaptureAnalysisOutcome


@pytest.fixture
def api_client():
    application = create_app(
        Settings(
            _env_file=None,
            api_v1_prefix="/api/v1",
            cors_origins="",
            jwt_secret_key="test-only-secret-key-with-at-least-32-chars",
        )
    )
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()


def test_health_route(api_client):
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_route_returns_bearer_token_and_profile(api_client):
    profile_id = uuid4()

    class FakeAuthService:
        def register(self, profile, password):
            assert password == "a-strong-password"
            return profile.model_copy(update={"id": str(profile_id)})

        def create_refresh_session(self, _user_id):
            return "refresh-token-for-tests"

    api_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = api_client.post(
        "/api/v1/auth/register",
        json={
            "name_or_nickname": "Ana",
            "email": "ANA@example.com",
            "objective": "weight_loss",
            "declared_allergies": ["amendoim"],
            "password": "a-strong-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["access_token"]
    assert response.json()["refresh_token"] == "refresh-token-for-tests"
    assert response.json()["token_type"] == "bearer"
    assert response.json()["user"]["id"] == str(profile_id)
    assert "password" not in response.json()["user"]


def test_invalid_profile_payload_is_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/register",
        json={
            "name_or_nickname": "Ana",
            "email": "not-an-email",
            "objective": "weight_loss",
            "password": "a-strong-password",
        },
    )

    assert response.status_code == 422


def test_missing_profile_returns_not_found(api_client):
    user_id = uuid4()

    class FakeProfileService:
        def get(self, _user_id):
            return None

    api_client.app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(user_id), name="Ana", email="ana@example.com", goal="weight_loss"
    )

    response = api_client.get(f"/api/v1/profiles/{user_id}")

    assert response.status_code == 404


def test_profile_route_hides_another_users_profile(api_client):
    authenticated_user_id = uuid4()
    requested_user_id = uuid4()

    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(authenticated_user_id),
        name="Ana",
        email="ana@example.com",
        goal="weight_loss",
    )

    response = api_client.get(f"/api/v1/profiles/{requested_user_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Resource not found"}


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
    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(user_id), name="Ana", email="ana@example.com", goal="weight_loss"
    )

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


def test_label_photo_route_extracts_and_records_label(api_client, monkeypatch):
    user_id = uuid4()
    product = Product(
        name="Produto fotografado",
        source=ProductSource.LABEL,
        ingredients_text="Açúcar, leite em pó",
    )

    class FakeWorkflowService:
        def capture_label_product(self, requested_user_id, extracted_product):
            assert requested_user_id == user_id
            assert extracted_product.name == "Produto fotografado"
            return CaptureAnalysisOutcome(
                capture_id=str(uuid4()),
                source_status="found",
                product=extracted_product,
                analysis=None,
            )

    from app.api import routes

    monkeypatch.setattr(routes, "extract_product_from_label", lambda _data, _mime: product)
    api_client.app.dependency_overrides[get_workflow_service] = lambda: FakeWorkflowService()
    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(user_id), name="Ana", email="ana@example.com", goal="weight_loss"
    )
    image_buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(image_buffer, format="PNG")

    response = api_client.post(
        f"/api/v1/profiles/{user_id}/captures/label-photo",
        files={"file": ("label.png", image_buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["source_status"] == "found"
    assert response.json()["product"]["source"] == "label"


def test_gemini_failure_returns_gateway_error_without_internal_details(api_client):
    user_id = uuid4()

    class FakeWorkflowService:
        def capture_ean(self, _requested_user_id, _ean):
            raise RuntimeError("provider failure containing internal details")

    api_client.app.dependency_overrides[get_workflow_service] = lambda: FakeWorkflowService()
    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(user_id), name="Ana", email="ana@example.com", goal="weight_loss"
    )

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
    api_client.app.dependency_overrides[get_current_profile] = lambda: UserProfile(
        id=str(user_id), name="Ana", email="ana@example.com", goal="weight_loss"
    )

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
