"""Custom authentication for OpenEO with development bypass."""

import os
import uuid
import logging
import base64
from typing import Optional

from fastapi import Header, HTTPException

from openeo_fastapi.client.auth import Authenticator, User, IssuerHandler
from openeo_fastapi.client.psql.engine import get_first_or_default, create, Filter
from openeo_fastapi.client.settings import AppSettings

logger = logging.getLogger(__name__)

# Development mode configuration
DEV_MODE = os.environ.get("OPENEO_DEV_MODE", "false").lower() == "true"
DEV_USER_ID = os.environ.get("OPENEO_DEV_USER_ID", "dev-user-001")


class DevAuthenticator(Authenticator):
    """
    Custom authenticator that supports:
    1. Development mode with Basic Auth bypass
    2. Production OIDC authentication
    """

    @staticmethod
    def validate(authorization: str = Header()) -> User:
        """
        Validate authorization and return user.

        In dev mode: Accepts Basic Auth with any credentials
        In prod mode: Requires valid OIDC Bearer token
        """
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check for Basic Auth in dev mode
        if DEV_MODE and authorization.lower().startswith("basic "):
            return DevAuthenticator._handle_basic_auth(authorization)

        # Check for Bearer token (OIDC)
        if authorization.lower().startswith("bearer "):
            return DevAuthenticator._handle_bearer_auth(authorization)

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization scheme. Use Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _handle_basic_auth(authorization: str) -> User:
        """Handle Basic Auth for development mode."""
        if not DEV_MODE:
            raise HTTPException(
                status_code=401,
                detail="Basic Auth only allowed in development mode",
            )

        try:
            # Decode Basic Auth
            encoded = authorization.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)

            logger.info(f"[DEV MODE] Basic Auth login: {username}")

            # Create or get dev user
            # DEV_USER_ID might not be a valid UUID, so generate one if needed
            try:
                dev_user_id = uuid.UUID(DEV_USER_ID) if DEV_USER_ID else uuid.uuid4()
            except ValueError:
                # If DEV_USER_ID is not a valid UUID, create a deterministic one from it
                dev_user_id = uuid.uuid5(uuid.NAMESPACE_DNS, DEV_USER_ID or "dev-user")
            oidc_sub = f"dev:{username}"

            # Check if user exists by oidc_sub
            found_user = get_first_or_default(
                User, Filter(column_name="oidc_sub", value=oidc_sub)
            )

            if found_user:
                logger.info(f"[DEV MODE] Found existing user: {found_user.user_id}")
                return found_user

            # Also check by user_id in case of conflict
            found_by_id = get_first_or_default(
                User, Filter(column_name="user_id", value=str(dev_user_id))
            )

            if found_by_id:
                logger.info(f"[DEV MODE] Found user by ID: {found_by_id.user_id}")
                return found_by_id

            # Create new dev user with a fresh UUID to avoid conflicts
            try:
                user = User(user_id=dev_user_id, oidc_sub=oidc_sub)
                create(create_object=user)
                logger.info(f"[DEV MODE] Created new user: {user.user_id}")
                return user
            except Exception as create_error:
                # If creation fails, try with a random UUID
                logger.warning(f"[DEV MODE] User creation conflict, using random UUID: {create_error}")
                user = User(user_id=uuid.uuid4(), oidc_sub=oidc_sub)
                create(create_object=user)
                logger.info(f"[DEV MODE] Created new user with random ID: {user.user_id}")
                return user

        except Exception as e:
            # Log full error internally but don't expose details to client
            logger.error(f"Basic Auth failed: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid Basic Auth credentials",
            )

    @staticmethod
    def _handle_bearer_auth(authorization: str) -> User:
        """Handle Bearer token (OIDC) authentication."""
        settings = AppSettings()

        try:
            policies = None
            if settings.OIDC_POLICIES:
                policies = settings.OIDC_POLICIES

            issuer = IssuerHandler(issuer_uri=settings.OIDC_URL, policies=policies)
            user_info = issuer.validate_token(authorization)

            # Check if user exists
            found_user = get_first_or_default(
                User, Filter(column_name="oidc_sub", value=user_info["sub"])
            )

            if found_user:
                return found_user

            # Create new user
            user = User(user_id=uuid.uuid4(), oidc_sub=user_info["sub"])
            create(create_object=user)

            return user

        except Exception as e:
            # Log full error internally but don't expose details to client
            logger.error(f"OIDC validation failed: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )


def get_auth_dependency():
    """Get the appropriate authentication dependency."""
    if DEV_MODE:
        logger.warning("Running in DEVELOPMENT MODE - Basic Auth enabled!")
    return DevAuthenticator.validate
