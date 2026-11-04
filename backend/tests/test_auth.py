from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_auth_service, get_current_profile, get_profile_service
from app.config.settings import Settings
from app.main import create_app
from app.models.user import UserProfile
from app.utils.passwords import hash_password, verify_password


@pytest.fixture
def auth_client():
    application = create_app(Settings(
        _env_file=None,
        api_v1_prefix="/api/v1",
        cors_origins="",
        jwt_secret_key="test-only-secret-key-with-at-least-32-chars",
    ))
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()


def test_login_returns_access_token(auth_client):
    user = UserProfile(
        id=str(uuid4()),
        name="Ana",
        email="ana@example.com",
        goal="weight_loss",
    )

    class FakeAuthService:
        def authenticate(self, email, password):
            assert email == "ana@example.com"
            assert password == "a-strong-password"
            return user

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "ANA@example.com", "password": "a-strong-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["user"]["id"] == user.id


def test_login_rejects_invalid_credentials_with_generic_response(auth_client):
    class FakeAuthService:
        def authenticate(self, _email, _password):
            return None

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_auth_me_requires_bearer_token(auth_client):
    response = auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_returns_authenticated_profile(auth_client):
    user = UserProfile(
        id=str(uuid4()),
        name="Ana",
        email="ana@example.com",
        goal="muscle_gain",
    )
    auth_client.app.dependency_overrides[get_current_profile] = lambda: user

    response = auth_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == user.id
    assert response.json()["name_or_nickname"] == "Ana"


def test_login_token_authenticates_request_to_auth_me(auth_client):
    user = UserProfile(
        id=str(uuid4()),
        name="Ana",
        email="ana@example.com",
        goal="weight_loss",
    )

    class FakeAuthService:
        def authenticate(self, _email, _password):
            return user

    class FakeProfileService:
        def get(self, user_id):
            assert str(user_id) == user.id
            return user

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    auth_client.app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()

    login_response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "a-strong-password"},
    )
    access_token = login_response.json()["access_token"]

    profile_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert profile_response.status_code == 200
    assert profile_response.json()["id"] == user.id


def test_password_is_hashed_and_can_be_verified():
    password = "a-strong-password"
    encoded_hash = hash_password(password)

    assert encoded_hash != password
    assert verify_password(password, encoded_hash)
    assert not verify_password("wrong-password", encoded_hash)
