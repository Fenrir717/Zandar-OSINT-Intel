from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from core.config import get_settings

ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(subject: str, ttl: timedelta, token_type: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(user_id: str) -> str:
    ttl = timedelta(minutes=get_settings().jwt_access_ttl_minutes)
    return _create_token(user_id, ttl, "access")


def create_refresh_token(user_id: str) -> str:
    ttl = timedelta(days=get_settings().jwt_refresh_ttl_days)
    return _create_token(user_id, ttl, "refresh")


def decode_token(token: str, expected_type: str = "access") -> str | None:
    """Kembalikan user_id bila token valid dan tipenya sesuai, selain itu None."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")
