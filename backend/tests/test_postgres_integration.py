"""Opt-in real PostgreSQL test, isolated from pytest application import order."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from dotenv import dotenv_values
import pytest
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
DATABASE = "nutriIA_test"


def _resolve_test_database_url(source, *, explicit=False):
    """Resolve without ever connecting to, logging or modifying the source DB."""
    url = make_url(source)
    if url.get_backend_name() not in {"postgresql", "postgres"}:
        raise ValueError("PostgreSQL is required")
    if explicit and url.database != DATABASE:
        raise ValueError("Explicit test URL must select nutriIA_test")
    return url.set(database=DATABASE).render_as_string(hide_password=False)


@pytest.mark.skipif(os.environ.get("NUTRIIA_RUN_DB_TESTS") != "1",
                    reason="Set NUTRIIA_RUN_DB_TESTS=1 to use nutriIA_test")
def test_postgres_registration_login_nutella_allergy_and_gemini_override():
    explicit = os.environ.get("NUTRIIA_TEST_DATABASE_URL")
    source = explicit or os.environ.get("DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
    if not source:
        pytest.fail("No PostgreSQL configuration available; no connection attempted", pytrace=False)
    environment = os.environ.copy()
    environment.update({
        "DATABASE_URL": _resolve_test_database_url(source, explicit=bool(explicit)),
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "NUTRITION_PROVIDER": "gemini",
        "GEMINI_ENRICHMENT_ENABLED": "false",
        "GEMINI_API_KEY": "not-used-integration-test-key",
        "API_V1_PREFIX": "/api/v1",
        "APP_ENV": "test",
    })
    result = subprocess.run([sys.executable, str(BACKEND / "tests" / "postgres_capture_worker.py")],
                            cwd=BACKEND, env=environment, capture_output=True, text=True, timeout=90)
    try:
        report = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        pytest.fail("Integration worker did not return a sanitized report", pytrace=False)
    if result.returncode != 0:
        pytest.fail(json.dumps(report), pytrace=False)
    if os.environ.get("NUTRIIA_AUDIT_REAL_OFF") == "1":
        print(json.dumps(report.get("benchmarks", [])))
    assert report["status"] == "passed"
    assert report["database"] == DATABASE
    assert report["guarded_writes"] > 0
    assert "favorable_gemini_rejected" in report["checks"]
    assert "rollback" in report["checks"]
    assert "exact_attempt_and_cache_origin" in report["checks"]
    assert "pending_history_isolation" in report["checks"]
    assert "personalized_history" in report["checks"]
    assert "quantitative_goal_change" in report["checks"]
    assert "ninho_serving_fallback" in report["checks"]
    assert "ingredient_quality_and_history" in report["checks"]
    assert "lactose_preference_warning" in report["checks"]


def test_test_database_url_never_selects_application_database():
    source = "postgresql://test_user:dummy@localhost/nutriIA?schema=public"
    assert make_url(_resolve_test_database_url(source)).database == DATABASE
    with pytest.raises(ValueError, match="Explicit test URL"):
        _resolve_test_database_url(source, explicit=True)
