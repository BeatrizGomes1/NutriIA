"""Fluxo da aplicação com banco para capturas, análises, cache e histórico."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config.settings import get_settings
from app.db.models import (
    AnalysisResultRecord,
    CaptureType,
    ProductCaptureRecord,
    ProductRecord,
    SourceStatus,
    UserProfileRecord,
)
from app.db.session import get_session_factory
from app.models.nutrition import AnalysisResult, Product
from app.models.user import UserProfile
from app.services.database_service import (
    analysis_to_domain,
    persist_analysis,
    product_to_domain,
    product_values,
    profile_to_domain,
)
from app.services.nutrition_service import NutritionService
from app.services.open_food_facts import OpenFoodFactsClient, ProductNotFoundError


@dataclass
class CaptureAnalysisOutcome:
    capture_id: str
    source_status: str
    product: Product | None
    analysis: AnalysisResult | None


def build_analysis_cache_key(
    user_id: UUID,
    product: Product,
    profile: UserProfile,
    *,
    provider: str,
    model: str,
    prompt_version: str,
) -> str:
    payload = {
        "user_id": str(user_id),
        "product": {
            "ean": product.ean,
            "name": product.name,
            "brand": product.brand,
            "ingredients": product.ingredients,
            "ingredients_text": product.ingredients_text,
            "serving_information": product.serving_information,
            "nutrition": product.nutrition.model_dump(mode="json"),
        },
        "profile": {
            "goal": str(profile.goal) if profile.goal is not None else None,
            "allergies": sorted(profile.allergies),
            "restrictions": sorted(profile.restrictions),
            "preferences": sorted(profile.preferences),
        },
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class NutritionWorkflowService:
    """Coordena consultas externas e persistência sem depender da camada HTTP."""

    def __init__(
        self,
        *,
        session_factory=None,
        open_food_facts: OpenFoodFactsClient | None = None,
        nutrition_service: NutritionService | None = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.open_food_facts = open_food_facts or OpenFoodFactsClient()
        self.nutrition_service = nutrition_service or NutritionService()

    def capture_ean(self, user_id: str | UUID, ean: str) -> CaptureAnalysisOutcome:
        uid = UUID(str(user_id))
        if not ean or not ean.strip():
            raise ValueError("EAN must not be empty")
        ean = ean.strip()

        # Confirma a existência do perfil antes de consultar o serviço externo.
        with self.session_factory() as session:
            if session.get(UserProfileRecord, uid) is None:
                raise LookupError(f"User profile {uid} was not found")

        try:
            fetched_product = self.open_food_facts.get_product(ean)
        except ProductNotFoundError:
            with self.session_factory() as session, session.begin():
                capture = ProductCaptureRecord(
                    user_id=uid,
                    capture_type=CaptureType.EAN,
                    ean=ean,
                    source_status=SourceStatus.NOT_FOUND,
                )
                session.add(capture)
                session.flush()
                capture_id = str(capture.id)
            return CaptureAnalysisOutcome(capture_id, SourceStatus.NOT_FOUND.value, None, None)

        fetched_values = product_values(fetched_product, fetched_at=datetime.now(timezone.utc))
        with self.session_factory() as session, session.begin():
            fetched_values["ean"] = ean
            # O Open Food Facts pode omitir campos. Mantém os últimos valores
            # conhecidos quando isso ocorrer e atualiza os campos retornados.
            # O upsert também trata dois processos importando o mesmo EAN.
            updates = {
                key: value
                for key, value in fetched_values.items()
                if key != "ean"
                and (key == "source_updated_at" or value is not None)
                and not (key == "ingredients_normalized" and not fetched_values["ingredients_raw"])
            }
            updates["updated_at"] = datetime.now(timezone.utc)
            statement = (
                pg_insert(ProductRecord)
                .values(**fetched_values)
                .on_conflict_do_update(index_elements=[ProductRecord.ean], set_=updates)
                .returning(ProductRecord)
            )
            record = session.scalars(statement).one()
            capture = ProductCaptureRecord(
                user_id=uid,
                product_id=record.id,
                capture_type=CaptureType.EAN,
                ean=ean,
                source_status=SourceStatus.FOUND,
            )
            session.add(capture)
            session.flush()
            capture_id = str(capture.id)
            product_id = record.id

        analysis = self.analyze_product(uid, product_id)
        with self.session_factory() as session:
            record = session.get(ProductRecord, product_id)
            product = product_to_domain(record)
        return CaptureAnalysisOutcome(capture_id, SourceStatus.FOUND.value, product, analysis)

    def analyze_product(self, user_id: str | UUID, product_id: str | UUID) -> AnalysisResult:
        uid, pid = UUID(str(user_id)), UUID(str(product_id))
        with self.session_factory() as session:
            profile_record = session.get(UserProfileRecord, uid)
            product_record = session.get(ProductRecord, pid)
            if profile_record is None:
                raise LookupError(f"User profile {uid} was not found")
            if product_record is None:
                raise LookupError(f"Product {pid} was not found")
            profile = profile_to_domain(profile_record)
            product = product_to_domain(product_record)

        settings = get_settings()
        provider_name = getattr(
            self.nutrition_service.provider,
            "name",
            self.nutrition_service.provider.__class__.__name__,
        )
        cache_key = build_analysis_cache_key(
            uid,
            product,
            profile,
            provider=provider_name,
            model=settings.gemini_model,
            prompt_version=settings.analysis_prompt_version,
        )
        cached = self._find_cached(cache_key)
        if cached is not None:
            return analysis_to_domain(cached, provider_name)

        result = self.nutrition_service.analyze(product, profile)
        try:
            with self.session_factory() as session, session.begin():
                current_product = session.get(ProductRecord, pid)
                row = persist_analysis(
                    session,
                    user_id=uid,
                    product=current_product,
                    result=result,
                    cache_key=cache_key,
                )
                session.flush()
                session.refresh(row)
                return analysis_to_domain(row, provider_name)
        except IntegrityError:
            # Outro processo pode ter gravado primeiro a chave única do cache.
            cached = self._find_cached(cache_key)
            if cached is None:
                raise
            return analysis_to_domain(cached, provider_name)

    def _find_cached(self, cache_key: str) -> AnalysisResultRecord | None:
        statement = (
            select(AnalysisResultRecord)
            .where(AnalysisResultRecord.cache_key == cache_key)
            .options(
                selectinload(AnalysisResultRecord.ingredient_matches),
                selectinload(AnalysisResultRecord.product),
            )
        )
        with self.session_factory() as session:
            return session.scalar(statement)
