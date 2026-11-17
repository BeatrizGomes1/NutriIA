"""Bounded, opt-in enrichment. Late answers never write to the database."""
from concurrent.futures import Future
from contextvars import ContextVar
from threading import BoundedSemaphore, Thread

OPTIONAL_TIMEOUT = ContextVar("optional_gemini_timeout", default=None)
_slots = BoundedSemaphore(2)


def enrich(baseline, context, provider, timeout):
    timeout = max(0.01, min(float(timeout), 10.0))
    if not _slots.acquire(blocking=False):
        return baseline
    future = Future()

    def call():
        token = OPTIONAL_TIMEOUT.set(timeout)
        try:
            future.set_result(provider(context))
        except Exception as error:
            future.set_exception(error)
        finally:
            OPTIONAL_TIMEOUT.reset(token)
            _slots.release()

    Thread(target=call, daemon=True, name="optional-gemini").start()
    try:
        from .analysis_provider import parse_provider_result
        response = future.result(timeout=timeout)
        verified = parse_provider_result(response, "optional_gemini", context)
        # Reject unsupported safety statements; never use a provider verdict.
        if (verified.status != baseline.status or verified.conflicts
                or not set(verified.reasons).issubset(baseline.reasons)):
            return baseline
        return baseline.model_copy(update={"reasons": verified.reasons, "evidence": verified.evidence})
    except Exception:
        return baseline
