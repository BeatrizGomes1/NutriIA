"""Account registration and credential verification."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update

from app.config.settings import get_settings
from app.db.models import PasswordResetTokenRecord, RefreshSessionRecord, UserProfileRecord
from app.db.session import get_session_factory
from app.models.user import UserProfile
from app.services.database_service import _profile_values, profile_to_domain
from app.utils.passwords import hash_password, verify_password


class AuthService:
    def __init__(self, session_factory=None, settings=None):
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()

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

    def create_refresh_session(self, user_id: UUID | str) -> str:
        if self.settings.refresh_token_expire_days < 1:
            raise RuntimeError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")
        raw_token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        record = RefreshSessionRecord(
            user_id=UUID(str(user_id)),
            family_id=uuid4(),
            token_hash=_token_hash(raw_token),
            expires_at=now + timedelta(days=self.settings.refresh_token_expire_days),
        )
        with self.session_factory() as session, session.begin():
            session.add(record)
        return raw_token

    def rotate_refresh_session(self, raw_token: str) -> tuple[UserProfile, str] | None:
        if not raw_token or len(raw_token) > 256:
            return None

        now = datetime.now(timezone.utc)
        new_raw_token = secrets.token_urlsafe(48)
        if self.settings.refresh_token_expire_days < 1:
            raise RuntimeError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")

        with self.session_factory() as session, session.begin():
            record = session.scalar(
                select(RefreshSessionRecord)
                .where(RefreshSessionRecord.token_hash == _token_hash(raw_token))
                .with_for_update()
            )
            if record is None:
                return None
            if record.revoked_at is not None:
                session.execute(
                    update(RefreshSessionRecord)
                    .where(
                        RefreshSessionRecord.family_id == record.family_id,
                        RefreshSessionRecord.revoked_at.is_(None),
                    )
                    .values(revoked_at=now)
                )
                return None
            if record.expires_at <= now:
                record.revoked_at = now
                return None

            profile_record = session.get(UserProfileRecord, record.user_id)
            if profile_record is None:
                record.revoked_at = now
                return None

            record.revoked_at = now
            rotated = RefreshSessionRecord(
                user_id=record.user_id,
                family_id=record.family_id,
                token_hash=_token_hash(new_raw_token),
                expires_at=now + timedelta(days=self.settings.refresh_token_expire_days),
            )
            session.add(rotated)
            session.flush()
            profile = profile_to_domain(profile_record)

        return profile, new_raw_token

    def issue_password_reset(self, email: str) -> tuple[str, str] | None:
        if self.settings.password_reset_token_expire_minutes < 1:
            raise RuntimeError("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be positive")

        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(48)
        with self.session_factory() as session, session.begin():
            profile = session.scalar(
                select(UserProfileRecord).where(UserProfileRecord.email == email.lower())
            )
            if profile is None:
                return None

            session.execute(
                update(PasswordResetTokenRecord)
                .where(
                    PasswordResetTokenRecord.user_id == profile.id,
                    PasswordResetTokenRecord.consumed_at.is_(None),
                )
                .values(consumed_at=now)
            )
            session.add(PasswordResetTokenRecord(
                user_id=profile.id,
                token_hash=_token_hash(raw_token),
                expires_at=now + timedelta(minutes=self.settings.password_reset_token_expire_minutes),
            ))

        return profile.email, raw_token

    def reset_password(self, raw_token: str, new_password: str) -> bool:
        if len(new_password) < 8 or len(new_password) > 128:
            raise ValueError("password must contain between 8 and 128 characters")
        if not raw_token or len(raw_token) > 256:
            return False

        now = datetime.now(timezone.utc)
        new_password_hash = hash_password(new_password)
        with self.session_factory() as session, session.begin():
            reset_record = session.scalar(
                select(PasswordResetTokenRecord)
                .where(PasswordResetTokenRecord.token_hash == _token_hash(raw_token))
                .with_for_update()
            )
            if (
                reset_record is None
                or reset_record.consumed_at is not None
                or reset_record.expires_at <= now
            ):
                return False

            profile = session.get(UserProfileRecord, reset_record.user_id)
            if profile is None:
                reset_record.consumed_at = now
                return False

            profile.password_hash = new_password_hash
            reset_record.consumed_at = now
            session.execute(
                update(RefreshSessionRecord)
                .where(
                    RefreshSessionRecord.user_id == profile.id,
                    RefreshSessionRecord.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            session.execute(
                update(PasswordResetTokenRecord)
                .where(
                    PasswordResetTokenRecord.user_id == profile.id,
                    PasswordResetTokenRecord.id != reset_record.id,
                    PasswordResetTokenRecord.consumed_at.is_(None),
                )
                .values(consumed_at=now)
            )
        return True

    def get(self, user_id: UUID) -> UserProfile | None:
        with self.session_factory() as session:
            record = session.get(UserProfileRecord, user_id)
            if record is None:
                return None
            return profile_to_domain(record)


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
