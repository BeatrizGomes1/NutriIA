from functools import lru_cache

from pwdlib import PasswordHash


_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password("not-a-real-user-password")


def verify_password(password: str, password_hash: str | None) -> bool:
    encoded_hash = password_hash or _dummy_password_hash()
    try:
        return _password_hasher.verify(password, encoded_hash)
    except Exception:
        return False
