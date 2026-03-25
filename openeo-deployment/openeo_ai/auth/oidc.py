"""
OIDC Authentication for OpenEO AI Assistant.

ABOUTME: Provides OIDCUser dataclass and FastAPI dependencies for authentication.
Integrates with the existing openeo-fastapi auth infrastructure.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from fastapi import Depends, HTTPException, Header

# Import from existing openeo_app auth
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from openeo_fastapi.client.auth import User

logger = logging.getLogger(__name__)

# Development mode configuration
DEV_MODE = os.environ.get("OPENEO_DEV_MODE", "false").lower() == "true"


@dataclass
class OIDCUser:
    """
    User information from OIDC authentication.

    This is a simplified view of the user for the AI assistant,
    wrapping the openeo-fastapi User model.
    """
    user_id: str
    oidc_sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    roles: list = field(default_factory=list)
    authenticated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_openeo_user(cls, user: User) -> "OIDCUser":
        """Create OIDCUser from openeo-fastapi User model."""
        return cls(
            user_id=str(user.user_id),
            oidc_sub=user.oidc_sub,
            # Email and name may be available in user_info from OIDC
            email=getattr(user, "email", None),
            name=getattr(user, "name", None),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "oidc_sub": self.oidc_sub,
            "email": self.email,
            "name": self.name,
            "roles": self.roles,
            "authenticated_at": self.authenticated_at.isoformat(),
        }


def _get_authenticator():
    """Get the appropriate authenticator based on environment."""
    # Import here to avoid circular imports
    try:
        from openeo_app.auth import DevAuthenticator
        return DevAuthenticator
    except ImportError:
        # Fallback to base authenticator
        from openeo_fastapi.client.auth import Authenticator
        return Authenticator


async def get_current_user(
    authorization: str = Header(..., description="Bearer token or Basic auth")
) -> OIDCUser:
    """
    FastAPI dependency to get the current authenticated user.

    Args:
        authorization: Authorization header (Bearer token or Basic auth in dev mode)

    Returns:
        OIDCUser: The authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    authenticator = _get_authenticator()

    try:
        # Use the existing authenticator
        user = authenticator.validate(authorization)
        return OIDCUser.from_openeo_user(user)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    authorization: Optional[str] = Header(None, description="Optional Bearer token")
) -> Optional[OIDCUser]:
    """
    FastAPI dependency for optional authentication.

    Returns None if no authorization header is provided,
    otherwise validates and returns the user.

    Args:
        authorization: Optional authorization header

    Returns:
        OIDCUser or None: The authenticated user or None
    """
    if not authorization:
        return None

    return await get_current_user(authorization)


def create_dev_user(username: str = "dev-user") -> OIDCUser:
    """
    Create a development user for testing.

    This should only be used in tests or development mode.

    Args:
        username: Username for the dev user

    Returns:
        OIDCUser: A development user instance
    """
    import uuid

    if not DEV_MODE and not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("create_dev_user can only be used in dev mode or tests")

    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
    return OIDCUser(
        user_id=user_id,
        oidc_sub=f"dev:{username}",
        email=f"{username}@dev.local",
        name=username.replace("-", " ").title(),
        roles=["user"],
    )
