import logging
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError

from app.api.schemas import (
    CaptureAnalysisResponse,
    CaptureHistoryResponse,
    EanCaptureRequest,
    LoginPayload,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfilePayload,
    ProfileResponse,
    RefreshPayload,
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
from app.gemini.nutrition_ai import extract_product_from_label
from app.models.nutrition import AnalysisResult
from app.models.user import UserProfile
from app.services.auth_service import AuthService
from app.services.database_service import HistoryService, ProfileService
from app.services.email_service import PasswordResetEmailService
from app.services.nutrition_workflow_service import NutritionWorkflowService


router = APIRouter()
logger = logging.getLogger(__name__)
MAX_LABEL_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class DatabaseUnavailable(RuntimeError):
    """The database connection could not be configured or reached."""


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_auth_service(settings: Settings = Depends(get_app_settings)) -> AuthService:
    validate_auth_settings(settings)
    try:
        return AuthService(settings=settings)
    except (RuntimeError, ValueError) as error:
        raise DatabaseUnavailable("Database is not configured") from error


def get_password_reset_email_service(
    settings: Settings = Depends(get_app_settings),
) -> PasswordResetEmailService:
    try:
        return PasswordResetEmailService(settings)
    except RuntimeError as error:
        raise AuthConfigurationError("Password reset email is not configured") from error


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


def _token_response(
    profile: UserProfile,
    settings: Settings,
    service: AuthService,
    refresh_token: str | None = None,
) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(profile.id, settings),
        refresh_token=refresh_token or service.create_refresh_session(profile.id),
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
    return _token_response(profile, settings, service)


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
    return _token_response(profile, settings, service)


@router.post("/auth/refresh", response_model=TokenResponse, tags=["auth"])
def refresh_session(
    payload: RefreshPayload,
    settings: Settings = Depends(get_app_settings),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    rotated = service.rotate_refresh_session(payload.refresh_token.get_secret_value())
    if rotated is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    profile, new_refresh_token = rotated
    return _token_response(profile, settings, service, new_refresh_token)


def _send_password_reset_safely(
    email_service: PasswordResetEmailService,
    email: str,
    token: str,
) -> None:
    try:
        email_service.send_password_reset(email, token)
    except Exception:
        logger.exception("Password reset email delivery failed")


@router.post("/auth/password-reset/request", status_code=202, tags=["auth"])
def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service),
    email_service: PasswordResetEmailService = Depends(get_password_reset_email_service),
) -> dict[str, str]:
    reset = service.issue_password_reset(payload.email)
    if reset is not None:
        email, token = reset
        background_tasks.add_task(_send_password_reset_safely, email_service, email, token)
    return {"message": "If the account exists, password reset instructions will be sent."}


@router.post("/auth/password-reset/confirm", tags=["auth"])
def confirm_password_reset(
    payload: PasswordResetConfirm,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    completed = service.reset_password(
        payload.token.get_secret_value(),
        payload.new_password.get_secret_value(),
    )
    if not completed:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    return {"message": "Password has been reset"}


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
    "/profiles/{user_id}/captures/label-photo",
    response_model=CaptureAnalysisResponse,
    tags=["products"],
)
def capture_product_by_label_photo(
    user_id: UUID,
    file: UploadFile = File(...),
    current_profile: UserProfile = Depends(get_current_profile),
    service: NutritionWorkflowService = Depends(get_workflow_service),
) -> CaptureAnalysisResponse:
    _ensure_owner(user_id, current_profile)
    expected_format = ALLOWED_IMAGE_FORMATS.get(file.content_type or "")
    if expected_format is None:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG and WEBP images are supported")

    image_data = file.file.read(MAX_LABEL_IMAGE_BYTES + 1)
    file.file.close()
    if not image_data or len(image_data) > MAX_LABEL_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be between 1 byte and 8 MB")

    try:
        with Image.open(BytesIO(image_data)) as image:
            if image.format != expected_format:
                raise HTTPException(status_code=415, detail="Image content does not match its media type")
            if image.width * image.height > 25_000_000:
                raise HTTPException(status_code=413, detail="Image resolution is too large")
            image.verify()
    except UnidentifiedImageError as error:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from error
    except Image.DecompressionBombError as error:
        raise HTTPException(status_code=413, detail="Image resolution is too large") from error
    except OSError as error:
        raise HTTPException(status_code=400, detail="Uploaded image is invalid or corrupted") from error

    product = extract_product_from_label(image_data, file.content_type)
    outcome = service.capture_label_product(user_id, product)
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
