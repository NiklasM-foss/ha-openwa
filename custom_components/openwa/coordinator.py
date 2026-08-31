"""Polls the OpenWA server for the state of the configured session."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenWaClient, OpenWaError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class OpenWaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps the session record from /api/sessions up to date.

    The endpoint returns every session on the server; we keep the one this
    config entry was set up for. A session that disappears (deleted in the
    dashboard) is reported as a failed update so the entities go unavailable
    instead of silently freezing on their last value.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenWaClient,
        session_id: str,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {session_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=entry,
        )
        self._client = client
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        """Return the session this coordinator follows."""
        return self._session_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the session record."""
        try:
            sessions = await self._client.list_sessions()
        except OpenWaError as err:
            raise UpdateFailed(str(err)) from err

        for session in sessions:
            if session.get("id") == self._session_id:
                return session

        raise UpdateFailed(f"Session {self._session_id} is no longer on the server")
