"""Serviços de persistência e adaptadores explícitos entre domínio e banco."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnalysisResultRecord,
    AnalysisVerdict,
    ConfidenceState,
    IngredientMatchRecord,
    IngredientMatchType,
    ProductCaptureRecord,
    ProductRecord,
    UserObjective,
    UserProfileRecord,
)
from app.db.session import get_session_factory
from app.models.nutrition import AnalysisResult, AnalysisStatus, NutritionFacts, Product, ProductSource
from app.models.user import DietaryGoal, UserProfile
from app.utils.helpers import normalize_text


class ProfileValidationError(ValueError):
    pass


def profile_to_domain(record: UserProfileRecord) -> UserProfile:
    goal = {
        UserObjective.WEIGHT_LOSS: DietaryGoal.WEIGHT_LOSS,
        UserObjective.MUSCLE_GAIN: DietaryGoal.MUSCLE_GAIN,
    }[record.objective]
    return UserProfile(
        id=str(record.id),
        name=record.name_or_nickname,
        email=record.email,
        age_range=record.age_range,
        onboarding_completed=record.onboarding_completed,
        goal=goal,
        allergies=list(record.declared_allergies or []),
        restrictions=list(record.avoided_ingredients or []),
        preferences=list(record.food_preferences or []),
    )


def _profile_values(profile: UserProfile) -> dict[str, Any]:
    if not profile.name or not profile.name.strip():
        raise ProfileValidationError("name is required by user_profiles.name_or_nickname")
    if not profile.email or not profile.email.strip():
        raise ProfileValidationError("email is required by user_profiles.email")
    try:
        objective = UserObjective(str(profile.goal))
    except (ValueError, TypeError) as error:
        raise ProfileValidationError("goal must be weight_loss or muscle_gain") from error
    return {
        "name_or_nickname": profile.name.strip(),
        "email": profile.email.strip().lower(),
        "age_range": profile.age_range,
        "objective": objective,
        "declared_allergies": list(profile.allergies),
        "avoided_ingredients": list(profile.restrictions),
        "food_preferences": list(profile.preferences),
        "onboarding_completed": profile.onboarding_completed,
    }


def product_to_domain(record: ProductRecord) -> Product:
    nutrition_data = record.nutrition_table or {}
    nutrition_data = nutrition_data.get("per_100g", nutrition_data)
    return Product(
        id=str(record.id),
        name=record.name,
        brand=record.brand,
        ean=record.ean,
        source=ProductSource.EAN if record.ean else ProductSource.UNKNOWN,
        ingredients_text=record.ingredients_raw,
        ingredients=list(record.ingredients_normalized or []),
        serving_information=record.serving_information,
        nutrition=NutritionFacts.model_validate(nutrition_data),
    )


def product_values(product: Product, *, fetched_at: datetime | None = None) -> dict[str, Any]:
    raw_ingredients = product.ingredients_text
    if raw_ingredients is None and product.ingredients:
        raw_ingredients = ", ".join(product.ingredients)
    parts = [part.strip() for part in re.split(r"[,;]", raw_ingredients or "") if part.strip()]
    normalized = list(dict.fromkeys(value for value in (normalize_text(part) for part in parts) if value))
    nutrition = product.nutrition.model_dump(mode="json", exclude_none=True)
    return {
        "ean": product.ean,
        "name": product.name,
        "brand": product.brand,
        "serving_information": product.serving_information,
        "nutrition_table": {"basis": "per_100g", "per_100g": nutrition} if nutrition else None,
        "ingredients_raw": raw_ingredients,
        "ingredients_normalized": normalized,
        "source_reference": f"https://world.openfoodfacts.org/product/{product.ean}" if product.ean else None,
        "source_updated_at": fetched_at or datetime.now(timezone.utc),
    }


class ProfileService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def create(self, profile: UserProfile) -> UserProfile:
        with self.session_factory() as session, session.begin():
            record = UserProfileRecord(**_profile_values(profile))
            session.add(record)
            session.flush()
            return profile_to_domain(record)

    def get(self, user_id: str | UUID) -> UserProfile | None:
        with self.session_factory() as session:
            record = session.get(UserProfileRecord, UUID(str(user_id)))
            return profile_to_domain(record) if record else None

    def update(self, user_id: str | UUID, profile: UserProfile) -> UserProfile | None:
        with self.session_factory() as session, session.begin():
            record = session.get(UserProfileRecord, UUID(str(user_id)))
            if record is None:
                return None
            for key, value in _profile_values(profile).items():
                setattr(record, key, value)
            session.flush()
            return profile_to_domain(record)


def _status_to_verdict(status: AnalysisStatus) -> AnalysisVerdict:
    return {
        AnalysisStatus.RECOMMENDED: AnalysisVerdict.RECOMMENDED,
        AnalysisStatus.ATTENTION: AnalysisVerdict.ATTENTION,
        AnalysisStatus.NOT_RECOMMENDED: AnalysisVerdict.AVOID,
        AnalysisStatus.INSUFFICIENT_INFORMATION: AnalysisVerdict.INSUFFICIENT,
    }[status]


def _verdict_to_status(verdict: AnalysisVerdict) -> AnalysisStatus:
    return {
        AnalysisVerdict.RECOMMENDED: AnalysisStatus.RECOMMENDED,
        AnalysisVerdict.ATTENTION: AnalysisStatus.ATTENTION,
        AnalysisVerdict.AVOID: AnalysisStatus.NOT_RECOMMENDED,
        AnalysisVerdict.INSUFFICIENT: AnalysisStatus.INSUFFICIENT_INFORMATION,
    }[verdict]


def persist_analysis(
    session: Session,
    *,
    user_id: UUID,
    product: ProductRecord,
    result: AnalysisResult,
    cache_key: str,
) -> AnalysisResultRecord:
    alerts = list(dict.fromkeys(
        conflict.evidence
        for conflict in result.conflicts
        if conflict.category in {"allergy", "restriction"}
    ))
    matched_restrictions = list(dict.fromkeys(
        conflict.profile_item
        for conflict in result.conflicts
        if conflict.category in {"allergy", "restriction"}
    ))
    row = AnalysisResultRecord(
        user_id=user_id,
        product_id=product.id,
        cache_key=cache_key,
        verdict=_status_to_verdict(result.status),
        ui_label={
            AnalysisStatus.RECOMMENDED: "Recomendado",
            AnalysisStatus.ATTENTION: "Atenção",
            AnalysisStatus.NOT_RECOMMENDED: "Evitar",
            AnalysisStatus.INSUFFICIENT_INFORMATION: "Informações insuficientes",
        }[result.status],
        summary=result.summary,
        critical_alerts=alerts,
        reasons=result.reasons,
        matched_restrictions=matched_restrictions,
        confidence_state=(
            ConfidenceState.INSUFFICIENT
            if result.status == AnalysisStatus.INSUFFICIENT_INFORMATION
            else ConfidenceState.SUFFICIENT
        ),
    )
    for conflict in result.conflicts:
        match_type = {
            "allergy": IngredientMatchType.ALLERGEN,
            "restriction": IngredientMatchType.AVOIDED_INGREDIENT,
            "preference": IngredientMatchType.PREFERENCE,
        }.get(conflict.category)
        if match_type is None:
            continue
        raw_name = conflict.term[:240]
        row.ingredient_matches.append(IngredientMatchRecord(
            raw_name=raw_name,
            normalized_name=normalize_text(raw_name)[:240],
            match_type=match_type,
            matched_profile_term=conflict.profile_item[:240],
            explanation=conflict.evidence,
            evidence_reference=conflict.source_excerpt or None,
        ))
    saved_conflict_evidence = {
        conflict.source_excerpt for conflict in result.conflicts if conflict.source_excerpt
    }
    for excerpt in result.evidence:
        if excerpt and excerpt not in saved_conflict_evidence:
            row.ingredient_matches.append(IngredientMatchRecord(
                raw_name=excerpt[:240],
                normalized_name=normalize_text(excerpt)[:240],
                match_type=IngredientMatchType.NONE,
                matched_profile_term=None,
                explanation="Trecho de evidência da análise.",
                evidence_reference=excerpt,
            ))
    session.add(row)
    session.flush()
    return row


def analysis_to_domain(row: AnalysisResultRecord, provider: str = "persisted") -> AnalysisResult:
    conflicts = []
    for match in row.ingredient_matches:
        if match.match_type in {IngredientMatchType.NONE, IngredientMatchType.HIDDEN_TERM}:
            continue
        category = {
            IngredientMatchType.ALLERGEN: "allergy",
            IngredientMatchType.AVOIDED_INGREDIENT: "restriction",
            IngredientMatchType.PREFERENCE: "preference",
        }.get(match.match_type, "restriction")
        conflicts.append({
            "term": match.raw_name,
            "category": category,
            "profile_item": match.matched_profile_term or match.raw_name,
            "evidence": match.explanation,
            "source_excerpt": match.evidence_reference or "",
        })
    return AnalysisResult(
        id=str(row.id),
        created_at=row.created_at,
        status=_verdict_to_status(row.verdict),
        product_name=row.product.name if row.product else None,
        summary=row.summary,
        reasons=list(row.reasons or []),
        conflicts=conflicts,
        evidence=list(dict.fromkeys(
            match.evidence_reference for match in row.ingredient_matches if match.evidence_reference
        )),
        provider=provider,
    )


class HistoryService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def list(self, user_id: str | UUID, *, limit: int = 20, offset: int = 0) -> list[AnalysisResult]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset must be non-negative")
        statement = (
            select(AnalysisResultRecord)
            .where(AnalysisResultRecord.user_id == UUID(str(user_id)))
            .options(selectinload(AnalysisResultRecord.ingredient_matches), selectinload(AnalysisResultRecord.product))
            .order_by(AnalysisResultRecord.created_at.desc(), AnalysisResultRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        with self.session_factory() as session:
            rows = session.scalars(statement).all()
            return [analysis_to_domain(row) for row in rows]

    def list_captures(
        self, user_id: str | UUID, *, limit: int = 20, offset: int = 0
    ) -> list[CaptureHistoryItem]:
        """Retorna o histórico de capturas, inclusive EANs não encontrados."""
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset must be non-negative")
        statement = (
            select(ProductCaptureRecord)
            .where(ProductCaptureRecord.user_id == UUID(str(user_id)))
            .options(selectinload(ProductCaptureRecord.product))
            .order_by(ProductCaptureRecord.captured_at.desc(), ProductCaptureRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        with self.session_factory() as session:
            captures = session.scalars(statement).all()
            results = []
            for capture in captures:
                product = product_to_domain(capture.product) if capture.product else None
                analysis = None
                if capture.product_id:
                    analysis_row = session.scalar(
                        select(AnalysisResultRecord)
                        .where(
                            AnalysisResultRecord.user_id == capture.user_id,
                            AnalysisResultRecord.product_id == capture.product_id,
                        )
                        .options(
                            selectinload(AnalysisResultRecord.ingredient_matches),
                            selectinload(AnalysisResultRecord.product),
                        )
                        .order_by(AnalysisResultRecord.created_at.desc())
                        .limit(1)
                    )
                    if analysis_row:
                        analysis = analysis_to_domain(analysis_row)
                results.append(CaptureHistoryItem(
                    capture_id=str(capture.id),
                    captured_at=capture.captured_at,
                    ean=capture.ean,
                    source_status=capture.source_status.value,
                    product=product,
                    analysis=analysis,
                ))
            return results


@dataclass
class CaptureHistoryItem:
    capture_id: str
    captured_at: datetime
    ean: str | None
    source_status: str
    product: Product | None
    analysis: AnalysisResult | None
