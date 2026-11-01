from uuid import UUID

from fastapi import APIRouter, Depends, Query
from app.models.nutrition import AnalysisResult
from app.services.database_service import HistoryService, ProfileService
from app.services.nutrition_workflow_service import NutritionWorkflowService
from app.api.schemas import (
    CaptureAnalysisResponse,
    CaptureHistoryResponse,
    EanCaptureRequest,
    ProfilePayload,
    ProfileResponse,
)


router = APIRouter()


class DatabaseUnavailable(RuntimeError):
    """The database connection could not be configured or reached."""


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


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Liveness endpoint; database and external providers are checked per request."""
    return {"status": "ok"}


@router.post("/profiles", response_model=ProfileResponse, status_code=201, tags=["profiles"])
def create_profile(
    payload: ProfilePayload,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return ProfileResponse.from_domain(service.create(payload.to_domain()))


@router.get("/profiles/{user_id}", response_model=ProfileResponse, tags=["profiles"])
def get_profile(
    user_id: UUID,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    profile = service.get(user_id)
    if profile is None:
        raise LookupError(f"User profile {user_id} was not found")
    return ProfileResponse.from_domain(profile)


@router.put("/profiles/{user_id}", response_model=ProfileResponse, tags=["profiles"])
def update_profile(
    user_id: UUID,
    payload: ProfilePayload,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
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
    service: NutritionWorkflowService = Depends(get_workflow_service),
) -> CaptureAnalysisResponse:
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
    service: NutritionWorkflowService = Depends(get_workflow_service),
) -> AnalysisResult:
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
    service: HistoryService = Depends(get_history_service),
) -> list[AnalysisResult]:
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
    service: HistoryService = Depends(get_history_service),
) -> list[CaptureHistoryResponse]:
    captures = service.list_captures(user_id, limit=limit, offset=offset)
    return [
        CaptureHistoryResponse.model_validate(capture, from_attributes=True)
        for capture in captures
    ]
