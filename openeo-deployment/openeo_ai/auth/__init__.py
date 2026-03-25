"""
OpenEO AI Authentication module.

ABOUTME: OIDC authentication wrapper for OpenEO AI Assistant.
Integrates with existing openeo-fastapi auth infrastructure.
"""

from .oidc import OIDCUser, get_current_user, get_optional_user

__all__ = ["OIDCUser", "get_current_user", "get_optional_user"]
