from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.schemas import (
    CaptureAnalysisResponse,
    CaptureHistoryResponse,
    EanCaptureRequest,
    LoginPayload,
    ProfilePayload,
    ProfileResponse,
    RegisterPayload,
    TokenResponse,
)
from app.api.security import (
    AuthConfigurationError,
    create_access_token,
    get_authenticated_user_id,
    validate_auth_settings,
)
from app.config.settings import Settings
from app.models.nutrition import AnalysisResult
from app.models.user import UserProfile
from app.services.auth_service import AuthService
from app.services.database_service import HistoryService, ProfileService
from app.services.nutrition_workflow_service import NutritionWorkflowService


router = APIRouter()


class DatabaseUnavailable(RuntimeError):
    """The database connection could not be configured or reached."""


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_auth_service(settings: Settings = Depends(get_app_settings)) -> AuthService:
    validate_auth_settings(settings)
    try:
        return AuthService()
    except (RuntimeError, ValueError) as error:
        raise DatabaseUnavailable("Database is not configured") from error


def get_profile_service() -> ProfileService:
    try:
        return ProfileService()
    except (RuntimeError, ValueError) as error:
        raise DatabaseUnavailable("Database is not configured") from error


def get_workflow_service() -> NutritionWorkflowService:
    try:
        return NutritionWorkflowService()
    except (RuntimeError, ValueError) as error:
        raise DatabaseUnavailable("Database is not configured") from error


def get_history_service() -> HistoryService:
    try:
        return HistoryService()
    except (RuntimeError, ValueError) as error:
        raise DatabaseUnavailable("Database is not configured") from error


def get_current_profile(
    user_id: UUID = Depends(get_authenticated_user_id),
    service: ProfileService = Depends(get_profile_service),
) -> UserProfile:
    profile = service.get(user_id)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return profile


def _ensure_owner(requested_user_id: UUID, profile: UserProfile) -> None:
    if str(requested_user_id) != profile.id:
        raise HTTPException(status_code=404, detail="Resource not found")


def _token_response(profile: UserProfile, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(profile.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
        user=ProfileResponse.from_domain(profile),
    )


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness endpoint; database and external providers are checked per request."""
    return {"status": "ok"}


@router.post("/auth/register", response_model=TokenResponse, status_code=201, tags=["auth"])
def register(
    payload: RegisterPayload,
    settings: Settings = Depends(get_app_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    profile = service.register(payload.to_domain(), payload.password.get_secret_value())
    return _token_response(profile, settings)


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(
    payload: LoginPayload,
    settings: Settings = Depends(get_app_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    profile = service.authenticate(payload.email, payload.password.get_secret_value())
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response(profile, settings)


@router.get("/auth/me", response_model=ProfileResponse, tags=["auth"])
def authenticated_profile(
    profile: UserProfile = Depends(get_current_profile),
) -> ProfileResponse:
    return ProfileResponse.from_domain(profile)


@router.get("/profiles/{user_id}", response_model=ProfileResponse, tags=["profiles"])
def get_profile(
    user_id: UUID,
    current_profile: UserProfile = Depends(get_current_profile),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    _ensure_owner(user_id, current_profile)
    profile = service.get(user_id)
    if profile is None:
        raise LookupError(f"User profile {user_id} was not found")
    return ProfileResponse.from_domain(profile)


@router.put("/profiles/{user_id}", response_model=ProfileResponse, tags=["profiles"])
def update_profile(
    user_id: UUID,
    payload: ProfilePayload,
    current_profile: UserProfile = Depends(get_current_profile),
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    _ensure_owner(user_id, current_profile)
    profile = service.update(user_id, payload.to_domain())
    if profile is None:
        raise LookupError(f"User profile {user_id} was not found")
    return ProfileResponse.from_domain(profile)


@router.post(
    "/profiles/{user_id}/captures/ean",
    response_model=CaptureAnalysisResponse,
    tags=["products"],
)
def capture_product_by_ean(
    user_id: UUID,
    payload: EanCaptureRequest,
    current_profile: UserProfile = Depends(get_current_profile),
    service: NutritionWorkflowService = Depends(get_workflow_service),
) -> CaptureAnalysisResponse:
    _ensure_owner(user_id, current_profile)
    outcome = service.capture_ean(user_id, payload.ean)
    return CaptureAnalysisResponse.model_validate(outcome, from_attributes=True)


@router.post(
    "/profiles/{user_id}/products/{product_id}/analysis",
    response_model=AnalysisResult,
    tags=["products"],
)
def analyze_saved_product(
    user_id: UUID,
    product_id: UUID,
    current_profile: UserProfile = Depends(get_current_profile),
    service: NutritionWorkflowService = Depends(get_workflow_service),
) -> AnalysisResult:
    _ensure_owner(user_id, current_profile)
    return service.analyze_product(user_id, product_id)


@router.get(
    "/profiles/{user_id}/history/analyses",
    response_model=list[AnalysisResult],
    tags=["history"],
)
def list_analysis_history(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_profile: UserProfile = Depends(get_current_profile),
    service: HistoryService = Depends(get_history_service),
) -> list[AnalysisResult]:
    _ensure_owner(user_id, current_profile)
    return service.list(user_id, limit=limit, offset=offset)


@router.get(
    "/profiles/{user_id}/history/captures",
    response_model=list[CaptureHistoryResponse],
    tags=["history"],
)
def list_capture_history(
    user_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_profile: UserProfile = Depends(get_current_profile),
    service: HistoryService = Depends(get_history_service),
) -> list[CaptureHistoryResponse]:
    _ensure_owner(user_id, current_profile)
    captures = service.list_captures(user_id, limit=limit, offset=offset)
    return [
        CaptureHistoryResponse.model_validate(capture, from_attributes=True)
        for capture in captures
    ]
