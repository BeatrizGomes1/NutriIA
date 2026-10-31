from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.routes import DatabaseUnavailable, router
from app.config.settings import Settings, get_settings
from app.services.database_service import ProfileValidationError
from app.services.open_food_facts import OpenFoodFactsError


def create_app(settings: Settings | None = None) -> FastAPI:
	settings = settings or get_settings()
	application = FastAPI(
		title="NutriIA API",
		version="0.1.0",
		description="API para perfis, produtos e análises nutricionais.",
	)

	if settings.cors_origins_list:
		application.add_middleware(
			CORSMiddleware,
			allow_origins=settings.cors_origins_list,
			allow_credentials=True,
			allow_methods=["GET", "POST", "PUT", "OPTIONS"],
			allow_headers=["Authorization", "Content-Type"],
		)

	@application.exception_handler(DatabaseUnavailable)
	async def database_unavailable_handler(
		_request: Request, _error: DatabaseUnavailable
	) -> JSONResponse:
		return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

	@application.exception_handler(IntegrityError)
	async def integrity_error_handler(
		_request: Request, _error: IntegrityError
	) -> JSONResponse:
		return JSONResponse(
			status_code=409,
			content={"detail": "The request conflicts with existing data"},
		)

	@application.exception_handler(SQLAlchemyError)
	async def database_error_handler(
		_request: Request, _error: SQLAlchemyError
	) -> JSONResponse:
		return JSONResponse(status_code=503, content={"detail": "Database operation failed"})

	@application.exception_handler(OpenFoodFactsError)
	async def product_source_error_handler(
		_request: Request, _error: OpenFoodFactsError
	) -> JSONResponse:
		return JSONResponse(
			status_code=502,
			content={"detail": "Product source is temporarily unavailable"},
		)

	@application.exception_handler(ProfileValidationError)
	async def profile_validation_handler(
		_request: Request, error: ProfileValidationError
	) -> JSONResponse:
		return JSONResponse(status_code=422, content={"detail": str(error)})

	@application.exception_handler(LookupError)
	async def not_found_handler(_request: Request, error: LookupError) -> JSONResponse:
		return JSONResponse(status_code=404, content={"detail": str(error)})

	@application.exception_handler(RuntimeError)
	async def provider_error_handler(
		_request: Request, _error: RuntimeError
	) -> JSONResponse:
		return JSONResponse(status_code=502, content={"detail": "Analysis provider failed"})

	@application.exception_handler(ValueError)
	async def invalid_value_handler(_request: Request, error: ValueError) -> JSONResponse:
		return JSONResponse(status_code=422, content={"detail": str(error)})

	application.include_router(router, prefix=settings.api_v1_prefix.rstrip("/"))
	return application


app = create_app()
