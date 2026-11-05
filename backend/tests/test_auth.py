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

        def create_refresh_session(self, _user_id):
            return "refresh-token-for-tests"

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "ANA@example.com", "password": "a-strong-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["refresh_token"] == "refresh-token-for-tests"
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

        def create_refresh_session(self, _user_id):
            return "refresh-token-for-tests"

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


def test_refresh_rotates_session_and_returns_new_tokens(auth_client):
    user = UserProfile(
        id=str(uuid4()),
        name="Ana",
        email="ana@example.com",
        goal="weight_loss",
    )

    class FakeAuthService:
        def rotate_refresh_session(self, token):
            assert token == "old-refresh-token-which-is-long-enough-for-the-request"
            return user, "new-refresh-token"

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "old-refresh-token-which-is-long-enough-for-the-request"},
    )

    assert response.status_code == 200
    assert response.json()["refresh_token"] == "new-refresh-token"
    assert response.json()["access_token"]


def test_password_reset_request_is_generic_for_unknown_email(auth_client):
    class FakeAuthService:
        def issue_password_reset(self, _email):
            return None

    class FakeEmailService:
        pass

    from app.api.routes import get_password_reset_email_service

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    auth_client.app.dependency_overrides[get_password_reset_email_service] = lambda: FakeEmailService()

    response = auth_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 202
    assert "If the account exists" in response.json()["message"]


def test_password_reset_confirm_uses_one_time_token(auth_client):
    class FakeAuthService:
        def reset_password(self, token, password):
            assert token == "reset-token-which-is-long-enough-for-validation"
            assert password == "new-strong-password"
            return True

    auth_client.app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()

    response = auth_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": "reset-token-which-is-long-enough-for-validation",
            "new_password": "new-strong-password",
        },
    )

    assert response.status_code == 200


def test_password_is_hashed_and_can_be_verified():
    password = "a-strong-password"
    encoded_hash = hash_password(password)

    assert encoded_hash != password
    assert verify_password(password, encoded_hash)
    assert not verify_password("wrong-password", encoded_hash)
