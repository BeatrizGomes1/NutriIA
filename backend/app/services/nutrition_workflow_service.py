"""Fluxo da aplicação com banco para capturas, análises, cache e histórico."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
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
from app.models.nutrition import AnalysisResult, Product, ProductSource
from app.models.user import UserProfile
from app.services.database_service import (
    analysis_to_domain,
    persist_analysis,
    product_to_domain,
    product_values,
    profile_to_domain,
)
from app.services import food_safety, nutrition_observations
from app.services.nutrition_service import NutritionService
from app.services.analysis_lock import analysis_lock
from app.services.open_food_facts import OpenFoodFactsClient, ProductNotFoundError


@dataclass
class CaptureAnalysisOutcome:
    capture_id: str
    source_status: str
    product: Product | None
    analysis: AnalysisResult | None
    request_id: str | None = None
    analysis_origin: str | None = None
    processing_status: str = "completed"


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
        "analysis_flow_version": "deterministic-first-v1",
        "optional_enrichment": get_settings().gemini_enrichment_enabled,
        "nutrition_schema_version": 2,
        "personalization_version": nutrition_observations.PERSONALIZATION_VERSION,
        "food_safety_rules_version": food_safety.RULES_VERSION,
        "user_id": str(user_id),
        "product": {
            "ean": product.ean,
            "name": product.name,
            "brand": product.brand,
            "ingredients": product.ingredients,
            "ingredients_text": product.ingredients_text,
            "food_safety": product.food_safety.model_dump(mode="json"),
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

    def capture_ean(self, user_id: str | UUID, ean: str, request_id: UUID | None = None) -> CaptureAnalysisOutcome:
        if request_id is None:
            return self._capture_ean(user_id, ean)
        uid = UUID(str(user_id))
        with self.session_factory() as session, session.begin():
            if session.get(UserProfileRecord, uid) is None:
                raise LookupError("Profile not found")
            statement = pg_insert(ProductCaptureRecord).values(
                user_id=uid, request_id=request_id, ean=ean.strip(), capture_type=CaptureType.EAN,
                source_status=SourceStatus.INSUFFICIENT, processing_status="pending"
            ).on_conflict_do_nothing(index_elements=[ProductCaptureRecord.request_id]).returning(ProductCaptureRecord.id)
            created = session.scalar(statement)
        if created is None:
            return self.request_result(uid, request_id, expected_ean=ean.strip())
        try:
            self._capture_ean(uid, ean, capture_id=created)
        except Exception:
            with self.session_factory() as session, session.begin():
                row = session.get(ProductCaptureRecord, created)
                row.processing_status = "completed" if row.analysis_id else "failed"
            raise
        return self.request_result(uid, request_id)

    def request_result(self, user_id, request_id, *, expected_ean=None):
        with self.session_factory() as session:
            row = session.scalar(select(ProductCaptureRecord).where(
                ProductCaptureRecord.request_id == request_id,
                ProductCaptureRecord.user_id == UUID(str(user_id))))
            if row is None:
                raise LookupError("Attempt not found")
            if expected_ean is not None and row.ean != expected_ean:
                raise ValueError("Request identifier already used for another product")
            analysis = None
            if row.analysis_id:
                saved = session.scalar(select(AnalysisResultRecord).where(
                    AnalysisResultRecord.id == row.analysis_id, AnalysisResultRecord.user_id == row.user_id,
                    AnalysisResultRecord.product_id == row.product_id).options(
                    selectinload(AnalysisResultRecord.ingredient_matches), selectinload(AnalysisResultRecord.product)))
                analysis = analysis_to_domain(saved) if saved else None
            product = product_to_domain(row.product) if row.product else None
            if product and row.capture_type == CaptureType.LABEL_PHOTO:
                product.source = ProductSource.LABEL
            return CaptureAnalysisOutcome(str(row.id), row.source_status.value,
                product, analysis,
                str(row.request_id), row.analysis_origin, row.processing_status or "unlinked")

    def _capture_ean(self, user_id: str | UUID, ean: str, *, capture_id=None) -> CaptureAnalysisOutcome:
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
                capture = session.get(ProductCaptureRecord, capture_id) if capture_id else ProductCaptureRecord(
                    user_id=uid, capture_type=CaptureType.EAN, ean=ean)
                capture.source_status = SourceStatus.NOT_FOUND
                capture.processing_status = "completed"
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
            # A safety declaration without nutrients must not erase the
            # nutrition reference/values preserved by the first P0 fix.
            safety = fetched_product.food_safety.model_dump(mode="json", exclude_defaults=True)
            if safety and not fetched_product.nutrition.has_any_value():
                updates["nutrition_table"] = func.coalesce(
                    ProductRecord.nutrition_table,
                    literal(fetched_values["nutrition_table"], type_=JSONB),
                ).op("||")(literal({"food_safety": safety}, type_=JSONB))
            updates["updated_at"] = datetime.now(timezone.utc)
            statement = (
                pg_insert(ProductRecord)
                .values(**fetched_values)
                .on_conflict_do_update(index_elements=[ProductRecord.ean], set_=updates)
                .returning(ProductRecord)
            )
            record = session.scalars(statement).one()
            capture = session.get(ProductCaptureRecord, capture_id) if capture_id else ProductCaptureRecord(
                user_id=uid, capture_type=CaptureType.EAN, ean=ean)
            capture.product_id = record.id
            capture.source_status = SourceStatus.FOUND
            capture.processing_status = "pending"
            session.add(capture)
            session.flush()
            capture_id = str(capture.id)
            product_id = record.id

        analysis = self.analyze_product(uid, product_id, capture_id=capture_id)
        with self.session_factory() as session:
            record = session.get(ProductRecord, product_id)
            product = product_to_domain(record)
        return CaptureAnalysisOutcome(capture_id, SourceStatus.FOUND.value, product, analysis)

    def capture_label_product(
        self, user_id: str | UUID, product: Product, *, request_id=None
    ) -> CaptureAnalysisOutcome:
        if request_id:
            with analysis_lock(f"photo-attempt:{user_id}:{request_id}"):
                try:
                    return self.request_result(user_id, request_id)
                except LookupError:
                    return self._capture_label_product(user_id, product, request_id=request_id)
        return self._capture_label_product(user_id, product)

    def _capture_label_product(self, user_id, product, *, request_id=None):
        uid = UUID(str(user_id))
        product = product.model_copy(update={"source": ProductSource.LABEL, "ean": None})
        source_status = (
            SourceStatus.FOUND
            if product.has_identity() and product.ingredient_text().strip()
            else SourceStatus.INSUFFICIENT
        )

        with self.session_factory() as session:
            if session.get(UserProfileRecord, uid) is None:
                raise LookupError(f"User profile {uid} was not found")

        values = product_values(product, fetched_at=datetime.now(timezone.utc))
        values["ean"] = None
        with self.session_factory() as session, session.begin():
            record = None
            if source_status == SourceStatus.FOUND and product.name:
                conditions = [
                    ProductRecord.ean.is_(None),
                    func.lower(ProductRecord.name) == product.name.lower(),
                    ProductRecord.ingredients_normalized == values["ingredients_normalized"],
                    ProductRecord.nutrition_table == values["nutrition_table"],
                    ProductRecord.serving_information.is_not_distinct_from(values["serving_information"]),
                ]
                if product.brand:
                    conditions.append(func.lower(ProductRecord.brand) == product.brand.lower())
                else:
                    conditions.append(ProductRecord.brand.is_(None))
                record = session.scalar(
                    select(ProductRecord)
                    .where(*conditions)
                    .order_by(ProductRecord.updated_at.desc())
                    .limit(1)
                    .with_for_update()
                )

            if record is None:
                record = ProductRecord(**values)
                session.add(record)
                session.flush()
            capture = ProductCaptureRecord(
                user_id=uid,
                product_id=record.id,
                capture_type=CaptureType.LABEL_PHOTO,
                source_status=source_status,
                request_id=request_id,
                processing_status="pending",
            )
            session.add(capture)
            session.flush()
            capture_id = str(capture.id)
            product_id = record.id

        analysis = self.analyze_product(uid, product_id, capture_id=capture_id)
        if request_id:
            return self.request_result(uid, request_id)
        with self.session_factory() as session:
            saved_record = session.get(ProductRecord, product_id)
            saved_product = product_to_domain(saved_record).model_copy(
                update={"source": ProductSource.LABEL}
            )
        return CaptureAnalysisOutcome(
            capture_id,
            source_status.value,
            saved_product,
            analysis,
        )

    def analyze_product(self, user_id: str | UUID, product_id: str | UUID, *, capture_id=None) -> AnalysisResult:
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
        with analysis_lock(cache_key):
            cached = self._find_cached(cache_key)
            if cached is not None:
                self._bind_capture(capture_id, cached.id, "cache")
                return analysis_to_domain(cached, "deterministic_nutrition")

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
                    self._bind_capture(capture_id, row.id, "generated", session=session)
                    return analysis_to_domain(row, "deterministic_nutrition")
            except IntegrityError:
                # Outro processo pode ter gravado primeiro a chave única do cache.
                cached = self._find_cached(cache_key)
                if cached is None:
                    raise
                self._bind_capture(capture_id, cached.id, "cache")
                return analysis_to_domain(cached, "deterministic_nutrition")

    def _bind_capture(self, capture_id, analysis_id, origin, *, session=None):
        if capture_id is None:
            return
        if session is None:
            with self.session_factory() as own, own.begin():
                self._bind_capture(capture_id, analysis_id, origin, session=own)
            return
        row = session.get(ProductCaptureRecord, UUID(str(capture_id)))
        row.analysis_id = analysis_id
        row.analysis_origin = origin
        row.processing_status = "completed"

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
