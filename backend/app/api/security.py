from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config.settings import Settings


BEARER_SCHEME = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "nutriia-api"


class AuthConfigurationError(RuntimeError):
    """Authentication cannot run because required signing configuration is missing."""


def _signing_key(settings: Settings) -> str:
    secret = settings.jwt_secret_key
    if not secret or len(secret) < 32 or secret.startswith("replace-with-"):
        raise AuthConfigurationError("JWT_SECRET_KEY must contain at least 32 characters")
    if settings.access_token_expire_minutes < 1:
        raise AuthConfigurationError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
    return secret


def validate_auth_settings(settings: Settings) -> None:
    _signing_key(settings)


def create_access_token(subject: UUID | str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, _signing_key(settings), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> UUID:
    payload = jwt.decode(
        token,
        _signing_key(settings),
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        options={"require": ["sub", "exp", "iss"]},
    )
    return UUID(payload["sub"])


def get_authenticated_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(BEARER_SCHEME),
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return decode_access_token(credentials.credentials, request.app.state.settings)
    except (jwt.InvalidTokenError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
