"""Thin async client for the OpenWA (rmyndharis/OpenWA) REST API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class OpenWaError(Exception):
    """Generic OpenWA API error."""


class OpenWaAuthError(OpenWaError):
    """Authentication failed (bad or missing API key)."""


class OpenWaConnectionError(OpenWaError):
    """Could not reach the OpenWA server."""


class OpenWaClient:
    """Minimal async wrapper around the OpenWA REST API."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, api_key: str
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._base = base_url.rstrip("/")
        self._headers = {"x-api-key": api_key}

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""
        return self._base

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                if resp.status in (401, 403):
                    raise OpenWaAuthError(f"Authentication failed ({resp.status})")
                if resp.status >= 400:
                    text = await resp.text()
                    raise OpenWaError(f"HTTP {resp.status}: {text[:300]}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return None
        except aiohttp.ClientError as err:
            raise OpenWaConnectionError(str(err)) from err
        except asyncio.TimeoutError as err:
            raise OpenWaConnectionError("Timeout talking to OpenWA") from err

    @staticmethod
    def _unwrap(data: Any) -> list[dict[str, Any]]:
        """OpenWA list endpoints return {value: [...], Count: n} or a bare list."""
        if isinstance(data, dict):
            value = data.get("value")
            if isinstance(value, list):
                return value
            return []
        if isinstance(data, list):
            return data
        return []

    async def list_sessions(self) -> list[dict[str, Any]]:
        """Return all WhatsApp sessions."""
        return self._unwrap(await self._request("GET", "/api/sessions"))

    async def send_text(
        self, session_id: str, chat_id: str, text: str
    ) -> dict[str, Any]:
        """Send a text message."""
        return await self._request(
            "POST",
            f"/api/sessions/{session_id}/messages/send-text",
            json={"chatId": chat_id, "text": text},
        )

    async def list_webhooks(self, session_id: str) -> list[dict[str, Any]]:
        """List webhooks registered for a session."""
        return self._unwrap(
            await self._request("GET", f"/api/sessions/{session_id}/webhooks")
        )

    async def create_webhook(
        self, session_id: str, url: str, events: list[str]
    ) -> dict[str, Any]:
        """Register a webhook subscription for a session."""
        return await self._request(
            "POST",
            f"/api/sessions/{session_id}/webhooks",
            json={"url": url, "events": events},
        )

    async def delete_webhook(self, session_id: str, webhook_id: str) -> None:
        """Delete a webhook subscription."""
        await self._request(
            "DELETE", f"/api/sessions/{session_id}/webhooks/{webhook_id}"
        )
