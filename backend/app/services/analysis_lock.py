"""Process-local single flight; database uniqueness remains the final arbiter."""
from contextlib import contextmanager
from threading import Lock
from weakref import WeakValueDictionary

_guard = Lock()
_locks = WeakValueDictionary()


@contextmanager
def analysis_lock(key):
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = Lock()
            _locks[key] = lock
    with lock:
        yield
