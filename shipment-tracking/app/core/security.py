import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import bcrypt
import jwt
from app.config import settings


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Generate JWT refresh token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except Exception:
        return None


def hash_api_key(api_key: str) -> str:
    """Compute SHA-256 hex hash of API key for secure database storage."""
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def generate_api_key(is_live: bool = True) -> Tuple[str, str, str]:
    """
    Generate an OpenAI/Stripe style high-entropy API key.
    Returns:
        (full_secret_key, key_prefix, key_hash)
    Example full key:
        cargotrk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
    """
    prefix = settings.API_KEY_LIVE_PREFIX if is_live else settings.API_KEY_TEST_PREFIX
    # 32 bytes = 64 hex characters of cryptographic entropy
    random_part = secrets.token_hex(20)
    full_key = f"{prefix}{random_part}"
    key_prefix = full_key[:18]  # e.g., 'cargotrk_live_a1b2'
    key_hash = hash_api_key(full_key)
    return full_key, key_prefix, key_hash
