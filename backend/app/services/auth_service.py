"""Account registration and credential verification."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserProfileRecord
from app.db.session import get_session_factory
from app.models.user import UserProfile
from app.services.database_service import _profile_values, profile_to_domain
from app.utils.passwords import hash_password, verify_password


class AuthService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def register(self, profile: UserProfile, password: str) -> UserProfile:
        if len(password) < 8 or len(password) > 128:
            raise ValueError("password must contain between 8 and 128 characters")

        record_values = _profile_values(profile)
        record_values["password_hash"] = hash_password(password)
        with self.session_factory() as session, session.begin():
            record = UserProfileRecord(**record_values)
            session.add(record)
            session.flush()
            return profile_to_domain(record)

    def authenticate(self, email: str, password: str) -> UserProfile | None:
        with self.session_factory() as session:
            record = session.scalar(
                select(UserProfileRecord).where(UserProfileRecord.email == email.lower())
            )
            encoded_hash = record.password_hash if record is not None else None
            profile = (
                profile_to_domain(record)
                if record is not None and encoded_hash is not None
                else None
            )

        if not verify_password(password, encoded_hash):
            return None
        return profile

    def get(self, user_id: UUID) -> UserProfile | None:
        with self.session_factory() as session:
            record = session.get(UserProfileRecord, user_id)
            if record is None:
                return None
            return profile_to_domain(record)
