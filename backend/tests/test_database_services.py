from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import (
    AnalysisVerdict,
    IngredientMatchType,
    UserObjective,
)
from app.models.nutrition import AnalysisStatus, Product
from app.models.user import DietaryGoal, UserProfile
from app.services.database_service import (
    ProfileValidationError,
    _profile_values,
    _status_to_verdict,
    analysis_to_domain,
    product_values,
    profile_to_domain,
)
from app.services.nutrition_workflow_service import build_analysis_cache_key
from app.db.session import sqlalchemy_url


def test_prisma_database_url_is_normalized_for_psycopg():
    url = sqlalchemy_url("postgresql://user:pass@localhost:5432/nutriia?schema=public&sslmode=require")

    assert url.drivername == "postgresql+psycopg"
    assert "schema" not in url.query
    assert url.query["sslmode"] == "require"


def test_profile_adapter_uses_database_terms_and_domain_fields():
    row = SimpleNamespace(
        id=uuid4(),
        name_or_nickname="Ana",
        email="ana@example.com",
        age_range="30-39",
        objective=UserObjective.WEIGHT_LOSS,
        declared_allergies=["amendoim"],
        avoided_ingredients=["açúcar"],
        food_preferences=["vegano"],
        onboarding_completed=True,
    )

    profile = profile_to_domain(row)

    assert profile.goal == DietaryGoal.WEIGHT_LOSS
    assert profile.allergies == ["amendoim"]
    assert profile.restrictions == ["açúcar"]
    assert profile.preferences == ["vegano"]
    assert _profile_values(profile)["objective"] == UserObjective.WEIGHT_LOSS


def test_profile_adapter_rejects_values_outside_database_enum():
    with pytest.raises(ProfileValidationError, match="weight_loss or muscle_gain"):
        _profile_values(UserProfile(name="Ana", email="ana@example.com", goal="unspecified"))


def test_product_adapter_normalizes_ingredients_and_keeps_per_100g_basis():
    values = product_values(Product(
        ean="1234567890123",
        ingredients_text="Açúcar, Óleo de palma; Sal",
    ))

    assert values["ingredients_raw"] == "Açúcar, Óleo de palma; Sal"
    assert values["ingredients_normalized"] == ["acucar", "oleo de palma", "sal"]
    assert values["nutrition_table"] is None
    assert values["source_reference"].endswith("1234567890123")


def test_analysis_verdict_and_persisted_matches_map_to_domain():
    assert _status_to_verdict(AnalysisStatus.NOT_RECOMMENDED) == AnalysisVerdict.AVOID
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        created_at=now,
        verdict=AnalysisVerdict.INSUFFICIENT,
        summary="Insuficiente",
        reasons=["Falta ingrediente"],
        product=SimpleNamespace(name="Produto"),
        ingredient_matches=[
            SimpleNamespace(
                match_type=IngredientMatchType.NONE,
                evidence_reference="rótulo indisponível",
            )
        ],
    )

    result = analysis_to_domain(row)

    assert result.status == AnalysisStatus.INSUFFICIENT_INFORMATION
    assert result.product_name == "Produto"
    assert result.evidence == ["rótulo indisponível"]
    assert result.conflicts == []


def test_analysis_cache_key_is_scoped_by_user_profile_and_model():
    product = Product(ean="1234567890123", ingredients_text="Açúcar")
    profile = UserProfile(goal="weight_loss", restrictions=["açúcar"])
    user_id = uuid4()
    base = build_analysis_cache_key(
        user_id, product, profile, provider="mock", model="m1", prompt_version="v0008"
    )

    assert base == build_analysis_cache_key(
        user_id, product, profile, provider="mock", model="m1", prompt_version="v0008"
    )
    assert base != build_analysis_cache_key(
        uuid4(), product, profile, provider="mock", model="m1", prompt_version="v0008"
    )
    assert base != build_analysis_cache_key(
        user_id, product, profile, provider="mock", model="m2", prompt_version="v0008"
    )
    assert base != build_analysis_cache_key(
        user_id, product, profile.model_copy(update={"preferences": ["vegano"]}),
        provider="mock", model="m1", prompt_version="v0008"
    )
