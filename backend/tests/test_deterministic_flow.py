import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.nutrition import Product
from app.models.user import UserProfile
from app.services.nutrition_service import NutritionService
from app.services import nutrition_service as service_module


def ninho():
    return Product(name="Ninho", ean="7891000325858", ingredients_text="Leite integral, minerais",
        nutrition={"basis": "per_serving", "serving_quantity": 25, "serving_unit": "g",
                   "protein_g": 6.3, "calories_kcal": 124, "fiber_g": 0})


def profile():
    return UserProfile(goal="muscle_gain", allergies=["Glúten"], preferences=["Sem lactose", "Baixo sódio"])


@pytest.mark.parametrize("mode", ["normal", "unavailable", "slow"])
def test_ninho_deterministic_result_survives_all_optional_provider_conditions(monkeypatch, mode):
    settings = SimpleNamespace(gemini_enrichment_enabled=False, gemini_enrichment_timeout_seconds=.02)
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    baseline = NutritionService(lambda _: pytest.fail("Disabled provider called")).analyze(ninho(), profile())
    completed = threading.Event()
    def provider(context):
        try:
            if mode == "unavailable": raise RuntimeError("offline")
            if mode == "slow": time.sleep(.15)
            return {"status": "recommended", "summary": "Seguro, consuma livremente", "reasons": []}
        finally: completed.set()
    settings.gemini_enrichment_enabled = True
    start = time.perf_counter()
    result = NutritionService(provider).analyze(ninho(), profile())
    assert time.perf_counter() - start < .14
    assert result.status == baseline.status == "attention"
    assert not result.conflicts
    assert set(result.reasons) == set(baseline.reasons)
    assert any("20.32%" in r for r in result.reasons)
    assert any("lactose" in r for r in result.reasons)
    assert "consuma livremente" not in str(result)
    snapshot = result.model_dump()
    assert completed.wait(2)
    assert result.model_dump() == snapshot


def test_confirmed_allergy_never_calls_even_enabled_optional_provider(monkeypatch):
    monkeypatch.setattr(service_module, "get_settings", lambda: SimpleNamespace(gemini_enrichment_enabled=True))
    result = NutritionService(lambda _: pytest.fail("Allergy must bypass provider")).analyze(
        ninho(), profile().model_copy(update={"allergies": ["leite"]}))
    assert result.status == "not_recommended" and result.conflicts


@pytest.mark.parametrize("nutrition", [{}, {"protein_g": 6.3, "basis": "unknown"}])
def test_missing_or_unknown_data_never_becomes_positive(nutrition):
    product = Product(name="Product", ingredients_text="water", nutrition=nutrition)
    result = NutritionService(lambda _: pytest.fail("Default flow must be local")).analyze(product, profile())
    assert result.status == "insufficient_information"
    assert not any("20.32%" in r or "6.3 g" in r for r in result.reasons)


def test_workflow_single_flight_rechecks_cache_before_calling_provider(monkeypatch):
    from app.services import nutrition_workflow_service as module
    product = ninho(); user = profile(); result = NutritionService().analyze(product, user)
    cache = {}; calls = []; entered = threading.Barrier(2)
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def begin(self): return self
        def get(self, *args): return object()
        def flush(self): pass
        def refresh(self, row): pass
    def provider(context):
        calls.append(1); time.sleep(.04)
        return {"status": "recommended", "summary": "Recomendado", "reasons": []}
    monkeypatch.setattr(service_module, "get_settings", lambda: SimpleNamespace(
        gemini_enrichment_enabled=True, gemini_enrichment_timeout_seconds=.5))
    workflow = module.NutritionWorkflowService(session_factory=Session,
        nutrition_service=NutritionService(provider))
    workflow._find_cached = lambda key: cache.get(key)
    monkeypatch.setattr(module, "profile_to_domain", lambda _: user)
    monkeypatch.setattr(module, "product_to_domain", lambda _: product)
    monkeypatch.setattr(module, "build_analysis_cache_key", lambda *a, **kw: "single-flight-test")
    def persist(*args, **kwargs):
        row = SimpleNamespace(id=uuid4()); cache["single-flight-test"] = row; return row
    monkeypatch.setattr(module, "persist_analysis", persist)
    monkeypatch.setattr(module, "analysis_to_domain", lambda *args: result)
    uid, pid = uuid4(), uuid4()
    def request():
        entered.wait(); return workflow.analyze_product(uid, pid)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: request(), range(2)))
    assert len(calls) == 1
    assert all(r.status == "attention" for r in results)
