import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_jwt_token, hash_api_key
from app.db.models import ApiKey, Tenant, User
from app.db.session import get_db

logger = logging.getLogger("shipment_tracking.auth")

http_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    tenant: Optional[Tenant] = None
    api_key: Optional[ApiKey] = None
    user: Optional[User] = None
    auth_type: str = "API_KEY"  # "API_KEY", "JWT", or "ANONYMOUS"
    scopes: List[str] = None

    def has_scope(self, scope: str) -> bool:
        if self.auth_type == "ANONYMOUS":
            return True
        if self.user and self.user.role in ("SUPER_ADMIN", "ADMIN"):
            return True
        if not self.scopes:
            return False
        return scope in self.scopes or "*" in self.scopes


def get_default_tenant(db: Session) -> Tenant:
    """Fetch or lazy-create the default enterprise tenant."""
    tenant = db.execute(
        select(Tenant).where(Tenant.slug == settings.DEFAULT_TENANT_SLUG)
    ).scalar_one_or_none()
    if not tenant:
        from app.db.session import seed_default_tenants
        seed_default_tenants(db)
        tenant = db.execute(
            select(Tenant).where(Tenant.slug == settings.DEFAULT_TENANT_SLUG)
        ).scalar_one_or_none()
    return tenant


async def get_current_auth(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Unified dual authentication dependency:
    1. Direct API Key header: 'X-API-Key: cargotrk_live_...'
    2. Bearer API Key header: 'Authorization: Bearer cargotrk_live_...'
    3. Bearer JWT Token: 'Authorization: Bearer <jwt_access_token>'
    4. Optional Anonymous Fallback for backwards compatibility with legacy tests/calls.
    """
    raw_api_key = x_api_key
    jwt_token = None

    if bearer and bearer.credentials:
        cred = bearer.credentials.strip()
        if cred.startswith(settings.API_KEY_LIVE_PREFIX) or cred.startswith(settings.API_KEY_TEST_PREFIX):
            raw_api_key = cred
        else:
            jwt_token = cred

    # 1. API Key Authentication
    if raw_api_key:
        raw_api_key = raw_api_key.strip()
        key_hash = hash_api_key(raw_api_key)
        api_key = db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        ).scalar_one_or_none()

        if not api_key or not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)
        if api_key.expires_at:
            exp = api_key.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key has expired.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        tenant = api_key.tenant
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant organization account is inactive or suspended.",
            )

        # Update last used timestamp
        api_key.last_used_at = now
        db.commit()

        scopes = [s.strip() for s in (api_key.scopes or "").split(",") if s.strip()]
        return AuthContext(
            tenant=tenant,
            api_key=api_key,
            user=None,
            auth_type="API_KEY",
            scopes=scopes,
        )

    # 2. JWT Bearer Authentication (User / Dashboard Session)
    if jwt_token:
        payload = decode_jwt_token(jwt_token)
        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token.")

        user = db.execute(select(User).where(User.id == int(user_id))).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled.")

        tenant = user.tenant
        if user.role != "SUPER_ADMIN":
            if not tenant or not tenant.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant organization is inactive.")
        else:
            if not tenant:
                tenant = get_default_tenant(db)

        scopes = ["*"] if user.role in ("SUPER_ADMIN", "ADMIN") else ["tracking:live", "tracking:read"]
        return AuthContext(
            tenant=tenant,
            api_key=None,
            user=user,
            auth_type="JWT",
            scopes=scopes,
        )

    # 3. Anonymous / Legacy Fallback
    if settings.ALLOW_ANONYMOUS_TRACKING:
        default_tenant = get_default_tenant(db)
        if not default_tenant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default tenant not configured.",
            )
        return AuthContext(
            tenant=default_tenant,
            api_key=None,
            user=None,
            auth_type="ANONYMOUS",
            scopes=["tracking:live", "tracking:read"],
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Authentication required. Live carrier tracking is metered and requires a valid API key via 'X-API-Key' header or "
            "an authenticated user session token via 'Authorization: Bearer <token>'."
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_scope(scope_name: str):
    """Dependency factory ensuring the authenticated client holds a required scope."""

    def _scope_checker(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if not auth.has_scope(scope_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission scope: '{scope_name}'.",
            )
        return auth

    return _scope_checker


def require_admin(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    """Dependency verifying the user has tenant administrator privileges."""
    if auth.auth_type == "ANONYMOUS":
        return auth
    if auth.user and auth.user.role in ("SUPER_ADMIN", "ADMIN"):
        return auth
    if auth.api_key and auth.has_scope("admin:manage"):
        return auth
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Administrator privilege required for this operation.",
    )


def require_super_admin(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    """Dependency verifying the caller is an authenticated SUPER_ADMIN user."""
    if auth.user and auth.user.role == "SUPER_ADMIN":
        return auth
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Superadmin privilege required for this operation.",
    )

