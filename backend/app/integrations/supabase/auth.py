"""Thin client for the Supabase Auth (GoTrue) password grant.

The application never stores a Supabase user's password locally. When Supabase
Auth is configured, login falls back to a one-shot password sign-in against
Supabase's ``/auth/v1/token`` endpoint, and the returned identity is mapped onto
the local ``users`` row used by the rest of the API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.exceptions import AuthenticationError, AuthServiceUnavailableError

logger = logging.getLogger("app")

_PASSWORD_GRANT_PARAMS = {"grant_type": "password"}


@dataclass(frozen=True)
class SupabaseIdentity:
    """Minimal identity returned by a successful Supabase password sign-in."""

    id: str
    email: str
    full_name: str


class SupabaseAuthClient:
    """Call Supabase Auth's token endpoint to validate an email/password pair."""

    def __init__(
        self,
        url: str,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def sign_in_with_password(self, email: str, password: str) -> SupabaseIdentity:
        """Validate credentials and return the canonical Supabase identity."""

        payload = self._post_token({"email": email.strip().lower(), "password": password})
        return self._identity_from(payload)

    def _post_token(self, credentials: dict[str, str]) -> dict[str, Any]:
        url = f"{self._url}/auth/v1/token"
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._client.post(
                url,
                headers=headers,
                json=credentials,
                params=_PASSWORD_GRANT_PARAMS,
            )
        except httpx.HTTPError as exc:
            logger.warning("Supabase Auth is unreachable: %s", exc)
            raise AuthServiceUnavailableError(
                "Unable to reach the authentication service. Please try again."
            ) from exc

        if response.status_code >= 500:
            logger.warning("Supabase Auth returned server error (status %s)", response.status_code)
            raise AuthServiceUnavailableError(
                "Unable to reach the authentication service. Please try again."
            )

        if response.status_code != 200:
            logger.info("Supabase Auth rejected credentials (status %s)", response.status_code)
            raise AuthenticationError("Invalid email or password")

        raw = response.json()
        if not isinstance(raw, dict):
            logger.warning("Supabase Auth returned an unexpected payload")
            raise AuthServiceUnavailableError(
                "Unable to reach the authentication service. Please try again."
            )
        data = cast(dict[str, Any], raw)
        if not isinstance(data.get("user"), dict):
            logger.warning("Supabase Auth returned an unexpected payload")
            raise AuthServiceUnavailableError(
                "Unable to reach the authentication service. Please try again."
            )
        return data

    @staticmethod
    def _identity_from(payload: dict[str, Any]) -> SupabaseIdentity:
        user = cast(dict[str, Any], payload.get("user"))
        email = str(user.get("email") or "").strip().lower()
        if not email:
            raise AuthenticationError("Invalid email or password")
        return SupabaseIdentity(
            id=str(user.get("id") or ""),
            email=email,
            full_name=SupabaseAuthClient._full_name(user),
        )

    @staticmethod
    def _full_name(user: dict[str, Any]) -> str:
        metadata = cast(dict[str, Any] | None, user.get("user_metadata"))
        if metadata:
            for key in ("full_name", "name", "fullName"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        email = str(user.get("email") or "")
        local_part = email.split("@", 1)[0]
        parts = [part for part in local_part.replace(".", " ").replace("_", " ").split() if part]
        name = " ".join(parts).title()
        return name or "Supabase User"
