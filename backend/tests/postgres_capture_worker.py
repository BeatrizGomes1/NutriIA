"""Isolated PostgreSQL integration scenario. Invoked by test_postgres_integration.

Only the parent process resolves credentials. No application module is imported
until DATABASE_URL is configured and the actual database identity is verified.
All changes are rolled back, including commits made by production services.
"""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import secrets
import sys
from unittest.mock import patch
from uuid import UUID, uuid4

EXPECTED_DATABASE = "nutriIA_test"
EAN = "3017620422003"
PERSONALIZED_EAN = "7896048706126"
GOAL_EAN = "0000000000000"
NINHO_EAN = "7891000325858"
MIOJO_EAN = "7891079011805"
phase = "configuration"


class IntegrationCheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise IntegrationCheckError(message)


def run():
    global phase
    # A fresh interpreter and this early check make import order explicit.
    require("app.main" not in sys.modules, "Application imported before database setup")
    require(bool(os.environ.get("DATABASE_URL")), "DATABASE_URL must be set before startup")
    from sqlalchemy import create_engine, event, select, func, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    url = make_url(os.environ["DATABASE_URL"])
    require(url.database == EXPECTED_DATABASE, "Refusing database other than nutriIA_test")
    require(url.get_backend_name() in {"postgres", "postgresql"}, "PostgreSQL is required")
    query = dict(url.query)
    query.pop("schema", None)
    query.setdefault("connect_timeout", "5")
    url = url.set(drivername="postgresql+psycopg", query=query)
    engine = create_engine(url, hide_parameters=True)
    verified_writes = []
    benchmarks = []

    @event.listens_for(engine, "connect")
    def check_connection(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            require(cursor.fetchone()[0] == EXPECTED_DATABASE,
                    "Database identity check failed; no writes permitted")
        dbapi_connection.rollback()

    @event.listens_for(engine, "before_cursor_execute")
    def check_each_write(connection, cursor, statement, parameters, context, executemany):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP", "TRUNCATE"}:
            cursor.execute("SELECT current_database()")
            require(cursor.fetchone()[0] == EXPECTED_DATABASE,
                    "Database identity check failed before write")
            require(verb in {"INSERT", "UPDATE"} or
                    verb == "ALTER" and statement.startswith("ALTER TABLE product_captures ADD COLUMN IF NOT EXISTS "),
                    "Unexpected destructive statement in integration test")
            verified_writes.append(verb)

    try:
        phase = "database identity"
        with engine.connect() as connection:
            require(connection.scalar(text("SELECT current_database()")) == EXPECTED_DATABASE,
                    "Database identity check failed")
            connection.rollback()

            # Import the real application only after checking the target DB.
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from fastapi.testclient import TestClient
            from app.api.security import decode_access_token
            from app.config.settings import get_settings
            from app.db.models import (CaptureType, SourceStatus, AnalysisResultRecord, ProductCaptureRecord,
                                       ProductRecord, RefreshSessionRecord, UserProfileRecord)
            from app.gemini import nutrition_ai
            from app.main import create_app
            from app.models.nutrition import AnalysisContext
            from app.services.analysis_provider import parse_provider_result
            from app.services.database_service import product_to_domain, profile_to_domain
            from app.services.open_food_facts import OpenFoodFactsClient
            import httpx

            session_factory = sessionmaker(bind=connection, expire_on_commit=False,
                                           join_transaction_mode="create_savepoint")
            @event.listens_for(session_factory, "before_flush")
            def emulate_independent_transaction_times(session, _context, _instances):
                # Production services start separate transactions. Here all
                # savepoints share one outer PostgreSQL now(), so use real UTC
                # instants for time-ordered rows without changing production.
                for record in session.new:
                    if isinstance(record, AnalysisResultRecord) and record.created_at is None:
                        record.created_at = datetime.now(timezone.utc)
                    elif isinstance(record, ProductCaptureRecord) and record.captured_at is None:
                        record.captured_at = datetime.now(timezone.utc)
            settings = get_settings()
            require(make_url(settings.database_url).database == EXPECTED_DATABASE,
                    "Application settings select the wrong database")
            application = create_app(settings)
            unique_email = f"integration-{uuid4().hex}@example.invalid"
            password = secrets.token_urlsafe(24)
            favorable = json.dumps({"status": "recommended", "summary": "Recomendado",
                                    "reasons": ["Sem conflitos"], "conflicts": [], "evidence": []})
            fixture = {"status": 1, "code": EAN, "product": {
                "product_name": "Nutella", "brands": "Ferrero",
                "ingredients_text": "Sugar, palm oil, hazelnuts (13%), skimmed milk powder (8.7%), cocoa",
                "allergens": "en:milk,en:nuts", "nutrition_data_per": "100g",
                "serving_size": "15 g", "nutriments": {
                    "energy-kcal_100g": 539, "sugars_100g": 56.3,
                    "carbohydrates_100g": 57.5, "proteins_100g": 6.3, "sodium_100g": .107}}}
            off_requests = []

            def off_handler(request):
                off_requests.append(request.url.path)
                if request.url.path.endswith(f"/product/{EAN}.json"):
                    return httpx.Response(200, json=fixture)
                if request.url.path.endswith(f"/product/{MIOJO_EAN}.json"):
                    return httpx.Response(200, json={"status": 1, "code": MIOJO_EAN, "product": {
                        "product_name": "Miojo", "ingredients_text":
                        "Valor energético (kcal) 333 Carboidratos (g) 41. Ingredientes do macarrão: "
                        "farinha de trigo, sal. ALÉRGICOS: CONTÉM LEITE. PODE CONTER SOJA.",
                        "allergens": "milk, wheat", "serving_size": "74 g", "nutrition_data_per": "serving",
                        "nutriments": {"proteins_serving": 6.22, "energy-kcal_serving": 246}}})
                if request.url.path.endswith(f"/product/{NINHO_EAN}.json"):
                    return httpx.Response(200, json={"status": 1, "code": NINHO_EAN, "product": {
                        "product_name": "LEITE PO NINHO INTEGRAL", "ingredients_text": "Leite integral",
                        "allergens": "milk", "nutrition_data_per": "100g", "serving_size": "25g",
                        "nutriments": {"proteins_100g": 25.2, "energy-kcal_100g": 496, "fiber_100g": 0,
                        "proteins_serving": 6.3, "energy-kcal_serving": 124, "fiber_serving": 0}}})
                if request.url.path.endswith(f"/product/{GOAL_EAN}.json"):
                    return httpx.Response(200, json={"status": 1, "code": GOAL_EAN, "product": {
                        "product_name": "Goal fixture", "ingredients_text": "water", "nutrition_data_per": "serving",
                        "serving_size": "30 g", "nutriments": {"energy-kcal_serving": 100,
                        "proteins_serving": 5, "fiber_serving": 2}}})
                require(request.url.path.endswith(f"/product/{PERSONALIZED_EAN}.json"), "Unexpected OFF request")
                return httpx.Response(200, json={"status": 1, "code": PERSONALIZED_EAN, "product": {
                    "product_name": "Leite Integral Zero Lactose", "ingredients_text": "Leite integral, enzima lactase",
                    "nutrition_data_per": "100g", "allergens": "en:milk", "serving_size": "26 g",
                    "nutriments": {"proteins_100g": 24.6, "sodium_100g": .36923}}})

            source = OpenFoodFactsClient(transport=httpx.MockTransport(off_handler))
            outer = connection.begin()
            original_capture_columns = set(connection.scalars(text(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'product_captures'")))
            # Test-only schema overlay: transactional DDL, rolled back with fixtures.
            # The versioned migration is NOT executed or marked as applied.
            for definition in (
                "request_id UUID UNIQUE", "analysis_id UUID REFERENCES analysis_results(id) ON DELETE SET NULL",
                "analysis_origin VARCHAR(16)", "processing_status VARCHAR(16)"):
                connection.execute(text("ALTER TABLE product_captures ADD COLUMN IF NOT EXISTS " + definition))
            original_product = connection.execute(
                select(ProductRecord.__table__).where(ProductRecord.ean == EAN)).mappings().one_or_none()
            original_product = dict(original_product) if original_product else None
            original_personalized_product = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == PERSONALIZED_EAN)).mappings().one_or_none()
            original_personalized_product = dict(original_personalized_product) if original_personalized_product else None
            original_goal_product = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == GOAL_EAN)).mappings().one_or_none()
            original_goal_product = dict(original_goal_product) if original_goal_product else None
            original_ninho = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == NINHO_EAN)).mappings().one_or_none()
            original_ninho = dict(original_ninho) if original_ninho else None
            original_miojo = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == MIOJO_EAN)).mappings().one_or_none()
            original_miojo = dict(original_miojo) if original_miojo else None
            second_email = f"integration-personalized-{uuid4().hex}@example.invalid"
            try:
                with patch("app.services.auth_service.get_session_factory", return_value=session_factory), \
                     patch("app.services.database_service.get_session_factory", return_value=session_factory), \
                     patch("app.services.nutrition_workflow_service.get_session_factory", return_value=session_factory), \
                     patch("app.services.nutrition_workflow_service.OpenFoodFactsClient", return_value=source), \
                     patch("app.gemini.nutrition_ai.generate_response", return_value=favorable) as gemini:
                    with TestClient(application) as client:
                        phase = "registration"
                        response = client.post("/api/v1/auth/register", json={
                            "name_or_nickname": "Integration Milk Allergy", "email": unique_email,
                            "password": password, "objective": "weight_loss",
                            "declared_allergies": ["leite"], "onboarding_completed": True})
                        require(response.status_code == 201, f"Registration HTTP {response.status_code}; expected 201")
                        registration = response.json()
                        user_id = UUID(registration["user"]["id"])
                        require(registration["user"]["declared_allergies"] == ["leite"], "Allergy not returned")
                        require(bool(registration.get("refresh_token")), "Registration refresh token missing")
                        require(decode_access_token(registration["access_token"], settings) == user_id,
                                "Registration access token invalid")

                        phase = "authentication"
                        denied = client.get("/api/v1/auth/me")
                        require(denied.status_code == 401, "Unauthenticated request was accepted")
                        response = client.post("/api/v1/auth/login", json={"email": unique_email, "password": password})
                        require(response.status_code == 200, f"Login HTTP {response.status_code}; expected 200")
                        login = response.json()
                        require(login.get("token_type") == "bearer" and login.get("expires_in", 0) > 0,
                                "Invalid token response contract")
                        require(decode_access_token(login["access_token"], settings) == user_id, "Login token invalid")
                        headers = {"Authorization": "Bearer " + login["access_token"]}
                        me = client.get("/api/v1/auth/me", headers=headers)
                        require(me.status_code == 200 and me.json()["id"] == str(user_id), "Bearer authentication failed")

                        phase = "EAN capture and deterministic safety"
                        endpoint = f"/api/v1/profiles/{user_id}/captures/ean"
                        response = client.post(endpoint, headers=headers, json={"ean": EAN})
                        require(response.status_code == 200, f"Capture HTTP {response.status_code}; expected 200")
                        captured = response.json()
                        require(captured["source_status"] == "found", "Product not found")
                        require(captured["product"]["ean"] == EAN and captured["product"]["name"] == "Nutella",
                                "Wrong product returned")
                        analysis = captured["analysis"]
                        require(analysis["status"] == "not_recommended", "Milk allergy was not enforced")
                        milk = [c for c in analysis["conflicts"]
                                if c["category"] == "allergy" and c["profile_item"] == "leite"]
                        require(bool(milk) and all(c["source_excerpt"] and c["evidence"] for c in milk),
                                "Missing traceable milk evidence")
                        require(any("milk powder" in c["source_excerpt"] for c in milk), "Milk derivative not detected")
                        require(bool(analysis["id"] and analysis["created_at"]), "Analysis was not persisted")
                        require(captured["product"]["nutrition"]["protein_g"] == 6.3,
                                "Nutrient value changed in persistence")
                        require(captured["product"]["nutrition"]["basis"] == "unknown",
                                "Ambiguous OFF reference was incorrectly inferred")
                        require(gemini.call_count == 0, "Confirmed conflict should bypass Gemini")

                        phase = "favorable Gemini response cannot override conflict"
                        with session_factory() as session:
                            record = session.get(UserProfileRecord, user_id)
                            require(record.password_hash != password, "Password was not hashed")
                            profile = profile_to_domain(record)
                            product = product_to_domain(session.get(ProductRecord, UUID(captured["product"]["id"])))
                        context = AnalysisContext(product=product, profile=profile.model_dump(mode="json"))
                        generated = nutrition_ai.generate_product_analysis(context.to_provider_payload())
                        require(json.loads(generated)["status"] == "recommended", "Gemini mock was not favorable")
                        reconciled = parse_provider_result(generated, "gemini", context)
                        require(reconciled.status == "not_recommended" and bool(reconciled.conflicts),
                                "Favorable Gemini result overrode deterministic safety")
                        require(gemini.call_count == 1, "Unexpected Gemini call count")

                        phase = "cache and history"
                        repeat = client.post(endpoint, headers=headers, json={"ean": EAN})
                        require(repeat.status_code == 200, f"Repeated capture HTTP {repeat.status_code}")
                        require(repeat.json()["analysis"]["id"] == analysis["id"], "Cache was not reused")
                        require(repeat.json()["analysis"]["status"] == "not_recommended", "Cached safety verdict changed")
                        history = client.get(f"/api/v1/profiles/{user_id}/history/captures", headers=headers)
                        require(history.status_code == 200 and bool(history.json()), "Capture history unavailable")
                        require(history.json()[0]["analysis"]["status"] == "not_recommended", "History lost safety verdict")
                        with session_factory() as session:
                            require(session.scalar(select(func.count()).select_from(AnalysisResultRecord)
                                .where(AnalysisResultRecord.user_id == user_id)) == 1, "Duplicate analysis persisted")
                            require(session.scalar(select(func.count()).select_from(ProductCaptureRecord)
                                .where(ProductCaptureRecord.user_id == user_id)) == 2, "Captures were not persisted")
                            token_hash = hashlib.sha256(login["refresh_token"].encode()).hexdigest()
                            require(session.scalar(select(func.count()).select_from(RefreshSessionRecord)
                                .where(RefreshSessionRecord.user_id == user_id,
                                       RefreshSessionRecord.token_hash == token_hash)) == 1,
                                "Refresh token hash was not persisted")
                        require(len(off_requests) == 2, "OFF transport not exercised")

                        phase = "personalized nutrition with gluten allergy"
                        second = client.post("/api/v1/auth/register", json={
                            "name_or_nickname": "Integration Personalized Nutrition", "email": second_email,
                            "password": password, "objective": "muscle_gain", "declared_allergies": ["Gl\u00faten"],
                            "food_preferences": ["Sem lactose", "Baixo s\u00f3dio"], "onboarding_completed": True})
                        require(second.status_code == 201, "Personalized registration failed")
                        second_id = second.json()["user"]["id"]
                        second_headers = {"Authorization": "Bearer " + second.json()["access_token"]}
                        second_endpoint = f"/api/v1/profiles/{second_id}/captures/ean"
                        personalized = client.post(second_endpoint, headers=second_headers, json={"ean": PERSONALIZED_EAN})
                        require(personalized.status_code == 200, "Personalized capture failed")
                        personal_analysis = personalized.json()["analysis"]
                        require(personal_analysis["status"] == "insufficient_information", "Unknown reference must not produce a quantitative verdict")
                        require(any("ganho de massa muscular" in r for r in personal_analysis["reasons"]), "Goal explanation lost")
                        require(any("Zero Lactose" in r for r in personal_analysis["reasons"]), "Lactose declaration lost")
                        require(any("Baixo s\u00f3dio" in r for r in personal_analysis["reasons"]), "Sodium preference lost")
                        require(not personal_analysis["conflicts"], "Preference misclassified as safety conflict")
                        require("369" not in " ".join(personal_analysis["reasons"]), "Unknown basis used quantitatively")
                        repeated_personal = client.post(second_endpoint, headers=second_headers, json={"ean": PERSONALIZED_EAN})
                        require(repeated_personal.status_code == 200, "Repeated personalized capture failed")
                        require(repeated_personal.json()["analysis"]["id"] == personal_analysis["id"], "Personalized cache not reused")
                        personal_history = client.get(f"/api/v1/profiles/{second_id}/history/captures", headers=second_headers)
                        require(personal_history.status_code == 200, "Personalized history unavailable")
                        require(personal_history.json()[0]["analysis"]["reasons"] == personal_analysis["reasons"],
                                "History discarded personalized reasons")
                        require(gemini.call_count == 1 and len(off_requests) == 4, "Unexpected external mock calls")
                        phase = "quantitative goal assessment and goal change"
                        gain = client.post(second_endpoint, headers=second_headers, json={"ean": GOAL_EAN})
                        require(gain.status_code == 200, "Quantitative gain capture failed")
                        gain_analysis = gain.json()["analysis"]
                        require(any("20%" in r and "prote\u00ednas" in r for r in gain_analysis["reasons"]), "Protein share missing")
                        require(gain.json()["product"]["nutrition"]["fiber_g"] == 2, "Fibre was not persisted")
                        changed = client.put(f"/api/v1/profiles/{second_id}", headers=second_headers, json={
                            "name_or_nickname": "Integration Personalized Nutrition", "email": second_email,
                            "objective": "weight_loss", "declared_allergies": ["Gl\u00faten"],
                            "food_preferences": ["Sem lactose", "Baixo s\u00f3dio"], "onboarding_completed": True})
                        require(changed.status_code == 200, "Goal update failed")
                        loss = client.post(second_endpoint, headers=second_headers, json={"ean": GOAL_EAN})
                        require(loss.status_code == 200, "Quantitative loss capture failed")
                        loss_analysis = loss.json()["analysis"]
                        require(loss_analysis["id"] != gain_analysis["id"], "Goal change reused previous cache")
                        require(any("densidade energ\u00e9tica" in r for r in loss_analysis["reasons"]), "Energy density missing")
                        require(any("alto teor de fibras" in r for r in loss_analysis["reasons"]), "Fibre evaluation missing")
                        require(not any("20% da energia" in r for r in loss_analysis["reasons"]), "Wrong goal criteria retained")
                        goal_history = client.get(f"/api/v1/profiles/{second_id}/history/captures", headers=second_headers)
                        require(goal_history.status_code == 200, "Goal history unavailable")
                        latest = next(row for row in goal_history.json() if row["ean"] == GOAL_EAN)
                        require(latest["analysis"]["reasons"] == loss_analysis["reasons"], "Goal history lost new evaluation")
                        phase = "Ninho explicit serving fallback"
                        updated = client.put(f"/api/v1/profiles/{second_id}", headers=second_headers, json={
                            "name_or_nickname": "Integration Personalized Nutrition", "email": second_email,
                            "objective": "muscle_gain", "declared_allergies": ["Gl\u00faten"],
                            "food_preferences": ["Sem lactose", "Baixo s\u00f3dio"], "onboarding_completed": True})
                        require(updated.status_code == 200, "Ninho goal update failed")
                        ninho = client.post(second_endpoint, headers=second_headers, json={"ean": NINHO_EAN})
                        require(ninho.status_code == 200, "Ninho capture failed")
                        nutrition = ninho.json()["product"]["nutrition"]
                        require(nutrition["basis"] == "per_serving", "Ninho serving reference lost")
                        require((nutrition["protein_g"], nutrition["calories_kcal"], nutrition["fiber_g"]) == (6.3, 124, 0),
                                "Ninho mixed nutrient columns")
                        require(nutrition["serving_quantity"] == 25 and nutrition["serving_unit"] == "g", "Ninho portion lost")
                        require(any("20.32%" in r for r in ninho.json()["analysis"]["reasons"]), "Ninho protein share missing")
                        require(any("leite declarado" in r and "Sem lactose" in r
                            for r in ninho.json()["analysis"]["reasons"]), "Lactose preference warning missing")
                        require(not ninho.json()["analysis"]["conflicts"], "Preference became an allergy")
                        ninho_history = client.get(f"/api/v1/profiles/{second_id}/history/captures", headers=second_headers)
                        require(ninho_history.status_code == 200, "Ninho history failed")
                        saved_ninho = next(row for row in ninho_history.json() if row["ean"] == NINHO_EAN)
                        require(saved_ninho["product"]["nutrition"]["protein_g"] == 6.3, "Ninho persisted value changed")
                        phase = "Miojo contaminated ingredients and safety evidence"
                        miojo = client.post(second_endpoint, headers=second_headers, json={"ean": MIOJO_EAN})
                        require(miojo.status_code == 200, "Miojo capture failed")
                        cleaned = miojo.json()["product"]
                        require("kcal" not in cleaned["ingredients_text"], "Nutrients leaked into ingredients")
                        require(cleaned["food_safety"]["ingredients_status"] == "incomplete", "Partial list not marked")
                        require("kcal" in cleaned["food_safety"]["ingredient_source_text"], "Original evidence lost")
                        require(miojo.json()["analysis"]["status"] == "not_recommended", "Wheat allergy lost during cleanup")
                        require(bool(miojo.json()["analysis"]["conflicts"]), "Critical conflict lost")
                        cleaned_history = client.get(f"/api/v1/profiles/{second_id}/history/captures", headers=second_headers)
                        require(cleaned_history.status_code == 200, "Miojo history failed")
                        saved_miojo = next(row for row in cleaned_history.json() if row["ean"] == MIOJO_EAN)
                        require(saved_miojo["product"]["food_safety"] == cleaned["food_safety"], "Quality evidence not persisted")
                        phase = "exact attempt, cache origin and history isolation"
                        request_id = str(uuid4())
                        attempt = client.post(second_endpoint, headers=second_headers,
                            json={"ean": NINHO_EAN, "request_id": request_id})
                        require(attempt.status_code == 200, "Identified capture failed")
                        require(attempt.json()["processing_status"] == "completed", "Capture not completed")
                        require(attempt.json()["analysis_origin"] == "cache", "Cache origin not identified")
                        require(attempt.json()["analysis"]["id"] == ninho.json()["analysis"]["id"], "Wrong reused analysis")
                        lookup = f"/api/v1/profiles/{second_id}/captures/requests/{request_id}"
                        require(client.get(lookup, headers=second_headers).json()["capture_id"] == attempt.json()["capture_id"], "Attempt lookup changed capture")
                        count_before = len(off_requests)
                        repeated_attempt = client.post(second_endpoint, headers=second_headers,
                            json={"ean": NINHO_EAN, "request_id": request_id})
                        require(repeated_attempt.json()["capture_id"] == attempt.json()["capture_id"], "Duplicate capture for same request")
                        require(len(off_requests) == count_before, "Idempotent retry repeated OFF call")
                        require(client.post(second_endpoint, headers=second_headers,
                            json={"ean": MIOJO_EAN, "request_id": request_id}).status_code == 422, "Request ID reused for another product")
                        pending_request = uuid4()
                        with session_factory() as session, session.begin():
                            session.add(ProductCaptureRecord(user_id=UUID(second_id), product_id=UUID(ninho.json()["product"]["id"]),
                                capture_type=CaptureType.EAN, ean=NINHO_EAN, source_status=SourceStatus.FOUND,
                                request_id=pending_request, processing_status="pending"))
                        pending = client.get(f"/api/v1/profiles/{second_id}/captures/requests/{pending_request}", headers=second_headers)
                        require(pending.status_code == 200 and pending.json()["analysis"] is None, "Old analysis leaked into new attempt")
                        pending_history = client.get(f"/api/v1/profiles/{second_id}/history/captures", headers=second_headers)
                        pending_ninho = next(row for row in pending_history.json() if row["ean"] == NINHO_EAN)
                        require(pending_ninho["analysis"] is None and pending_ninho["processing_status"] == "pending", "History substituted old analysis")
                        if os.environ.get("NUTRIIA_AUDIT_REAL_OFF") == "1":
                            import time
                            phase = "live OFF deterministic benchmarks"
                            real_source = OpenFoodFactsClient()
                            with patch.object(source, "get_product", side_effect=real_source.get_product):
                                for ean, expected in ((NINHO_EAN, "attention"), (MIOJO_EAN, "not_recommended")):
                                    started = time.perf_counter()
                                    measured = client.post(second_endpoint, headers=second_headers,
                                        json={"ean": ean, "request_id": str(uuid4())})
                                    elapsed = time.perf_counter() - started
                                    require(measured.status_code == 200, "Live OFF capture failed")
                                    require(measured.json()["analysis"]["status"] == expected, "Live OFF deterministic verdict changed")
                                    benchmarks.append({"ean": ean, "http": measured.status_code,
                                        "seconds": round(elapsed, 4), "status": expected,
                                        "off": "real", "gemini": "not_called"})
            finally:
                outer.rollback()
            phase = "rollback verification"
            require(set(connection.scalars(text(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'product_captures'"))) == original_capture_columns,
                "Test schema overlay survived rollback")
            require(connection.scalar(select(func.count()).select_from(UserProfileRecord)
                .where(UserProfileRecord.email == unique_email)) == 0, "Test user survived rollback")
            restored_product = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == EAN)).mappings().one_or_none()
            restored_product = dict(restored_product) if restored_product else None
            require(restored_product == original_product, "Existing product changed after rollback")
            restored_personalized = connection.execute(select(ProductRecord.__table__)
                .where(ProductRecord.ean == PERSONALIZED_EAN)).mappings().one_or_none()
            restored_personalized = dict(restored_personalized) if restored_personalized else None
            require(restored_personalized == original_personalized_product, "Personalized product changed after rollback")
            require(connection.scalar(select(func.count()).select_from(UserProfileRecord)
                .where(UserProfileRecord.email == second_email)) == 0, "Personalized test user survived rollback")
            restored_goal = connection.execute(select(ProductRecord.__table__).where(ProductRecord.ean == GOAL_EAN)).mappings().one_or_none()
            restored_goal = dict(restored_goal) if restored_goal else None
            require(restored_goal == original_goal_product, "Goal fixture product changed after rollback")
            restored_ninho = connection.execute(select(ProductRecord.__table__).where(ProductRecord.ean == NINHO_EAN)).mappings().one_or_none()
            restored_ninho = dict(restored_ninho) if restored_ninho else None
            require(restored_ninho == original_ninho, "Ninho product changed after rollback")
            restored_miojo = connection.execute(select(ProductRecord.__table__).where(ProductRecord.ean == MIOJO_EAN)).mappings().one_or_none()
            restored_miojo = dict(restored_miojo) if restored_miojo else None
            require(restored_miojo == original_miojo, "Miojo product changed after rollback")
            require(bool(verified_writes), "No real PostgreSQL writes were exercised")
        return {"status": "passed", "database": EXPECTED_DATABASE,
                "checks": ["registration", "login_and_tokens", "bearer_authentication",
                           "ean_capture", "persisted_milk_conflict", "favorable_gemini_rejected",
                           "cache", "history", "personalized_nutrition", "personalized_history", "quantitative_goal_change", "ninho_serving_fallback", "ingredient_quality_and_history", "lactose_preference_warning", "exact_attempt_and_cache_origin", "pending_history_isolation", "rollback"],
                "guarded_writes": len(verified_writes), "benchmarks": benchmarks}
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(run()))
    except Exception as error:
        # Never print exception SQL, parameters, connection strings or tokens.
        original = getattr(error, "orig", None)
        print(json.dumps({"status": "failed", "phase": phase, "error_type": type(error).__name__,
                          "sqlstate": getattr(original, "sqlstate", None),
                          "message": str(error) if isinstance(error, IntegrationCheckError)
                                     else "Internal error details suppressed to protect credentials"}))
        sys.exit(1)
