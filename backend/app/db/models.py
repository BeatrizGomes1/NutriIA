"""Mapeamentos ORM do schema PostgreSQL existente; este módulo não cria DDL."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserObjective(StrEnum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"


class CaptureType(StrEnum):
    EAN = "ean"
    LABEL_PHOTO = "label_photo"


class SourceStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    INSUFFICIENT = "insufficient"


class AnalysisVerdict(StrEnum):
    RECOMMENDED = "recommended"
    ATTENTION = "attention"
    AVOID = "avoid"
    INSUFFICIENT = "insufficient"


class ConfidenceState(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class IngredientMatchType(StrEnum):
    ALLERGEN = "allergen"
    AVOIDED_INGREDIENT = "avoided_ingredient"
    PREFERENCE = "preference"
    HIDDEN_TERM = "hidden_term"
    NONE = "none"


def _enum_values(enum_type):
    return [member.value for member in enum_type]


class UserProfileRecord(Base):
    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name_or_nickname: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    age_range: Mapped[str | None] = mapped_column(String(40))
    objective: Mapped[UserObjective] = mapped_column(
        Enum(UserObjective, name="user_objective", values_callable=_enum_values, native_enum=True)
    )
    declared_allergies: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    avoided_ingredients: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    food_preferences: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ean: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str | None] = mapped_column(String(240))
    brand: Mapped[str | None] = mapped_column(String(160))
    serving_information: Mapped[dict | None] = mapped_column(JSONB)
    nutrition_table: Mapped[dict | None] = mapped_column(JSONB)
    ingredients_raw: Mapped[str | None] = mapped_column(Text)
    ingredients_normalized: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductCaptureRecord(Base):
    __tablename__ = "product_captures"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"))
    product_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))
    capture_type: Mapped[CaptureType] = mapped_column(
        Enum(CaptureType, name="capture_type", values_callable=_enum_values, native_enum=True)
    )
    ean: Mapped[str | None] = mapped_column(String(32))
    image_reference: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status", values_callable=_enum_values, native_enum=True)
    )
    product: Mapped[ProductRecord | None] = relationship()


class AnalysisResultRecord(Base):
    __tablename__ = "analysis_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"))
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    cache_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    verdict: Mapped[AnalysisVerdict] = mapped_column(
        Enum(AnalysisVerdict, name="analysis_verdict", values_callable=_enum_values, native_enum=True)
    )
    ui_label: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    critical_alerts: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    matched_restrictions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    confidence_state: Mapped[ConfidenceState] = mapped_column(
        Enum(ConfidenceState, name="confidence_state", values_callable=_enum_values, native_enum=True)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ingredient_matches: Mapped[list["IngredientMatchRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="IngredientMatchRecord.id"
    )
    product: Mapped[ProductRecord] = relationship()


class IngredientMatchRecord(Base):
    __tablename__ = "ingredient_matches"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analysis_results.id", ondelete="CASCADE")
    )
    raw_name: Mapped[str] = mapped_column(String(240))
    normalized_name: Mapped[str] = mapped_column(String(240))
    match_type: Mapped[IngredientMatchType] = mapped_column(
        Enum(IngredientMatchType, name="ingredient_match_type", values_callable=_enum_values, native_enum=True)
    )
    matched_profile_term: Mapped[str | None] = mapped_column(String(240))
    explanation: Mapped[str] = mapped_column(Text)
    evidence_reference: Mapped[str | None] = mapped_column(Text)


Index("products_name_brand_idx", ProductRecord.name, ProductRecord.brand)
Index("product_captures_user_id_captured_at_idx", ProductCaptureRecord.user_id, ProductCaptureRecord.captured_at.desc())
Index("analysis_results_user_id_created_at_idx", AnalysisResultRecord.user_id, AnalysisResultRecord.created_at.desc())
