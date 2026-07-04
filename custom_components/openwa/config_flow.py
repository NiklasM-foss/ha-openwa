"""Config flow for the OpenWA (WhatsApp) integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    OpenWaAuthError,
    OpenWaClient,
    OpenWaConnectionError,
    OpenWaError,
)
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_DEFAULT_RECIPIENT,
    CONF_SESSION_ID,
    CONF_SESSION_NAME,
    CONF_SESSION_PHONE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _normalise_url(raw: str) -> str:
    """Ensure the base URL has a scheme and no trailing slash."""
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    return raw.rstrip("/")


def _session_label(session: dict[str, Any]) -> str:
    """Build a human friendly label for a session."""
    name = session.get("name") or session.get("pushName") or "WhatsApp"
    phone = session.get("phone")
    status = session.get("status")
    parts = [name]
    if phone:
        parts.append(f"+{phone}")
    if status:
        parts.append(f"[{status}]")
    return " ".join(parts)


class OpenWaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the GUI configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._base_url: str | None = None
        self._api_key: str | None = None
        self._sessions: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_url = _normalise_url(user_input[CONF_BASE_URL])
            api_key = user_input[CONF_API_KEY].strip()
            client = OpenWaClient(
                async_get_clientsession(self.hass), base_url, api_key
            )
            try:
                sessions = await client.list_sessions()
            except OpenWaAuthError:
                errors["base"] = "invalid_auth"
            except OpenWaConnectionError:
                errors["base"] = "cannot_connect"
            except OpenWaError:
                errors["base"] = "unknown"
            else:
                if not sessions:
                    errors["base"] = "no_sessions"
                else:
                    self._base_url = base_url
                    self._api_key = api_key
                    self._sessions = sessions
                    if len(sessions) == 1:
                        return await self._create_entry(sessions[0])
                    return await self.async_step_session()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_URL, default="http://192.168.1.10:2785"
                ): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_session(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: pick a session when several exist."""
        if user_input is not None:
            chosen = next(
                (s for s in self._sessions if s.get("id") == user_input[CONF_SESSION_ID]),
                None,
            )
            if chosen is not None:
                return await self._create_entry(chosen)

        options = [
            SelectOptionDict(value=s["id"], label=_session_label(s))
            for s in self._sessions
            if s.get("id")
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_SESSION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.LIST
                    )
                )
            }
        )
        return self.async_show_form(step_id="session", data_schema=schema)

    async def _create_entry(self, session: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry for the chosen session."""
        session_id = session["id"]
        assert self._base_url is not None
        await self.async_set_unique_id(f"{self._base_url}::{session_id}")
        self._abort_if_unique_id_configured()

        title = _session_label(session)
        return self.async_create_entry(
            title=title,
            data={
                CONF_BASE_URL: self._base_url,
                CONF_API_KEY: self._api_key,
                CONF_SESSION_ID: session_id,
                CONF_SESSION_NAME: session.get("name"),
                CONF_SESSION_PHONE: session.get("phone"),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return OpenWaOptionsFlow()


class OpenWaOptionsFlow(OptionsFlow):
    """Options: default recipient for the notify entity."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            recipient = user_input.get(CONF_DEFAULT_RECIPIENT, "").strip()
            return self.async_create_entry(
                title="", data={CONF_DEFAULT_RECIPIENT: recipient}
            )

        current = self.config_entry.options.get(CONF_DEFAULT_RECIPIENT, "")
        schema = vol.Schema(
            {vol.Optional(CONF_DEFAULT_RECIPIENT, default=current): str}
        )
        return self.async_show_form(step_id="init", data_schema=schema)
