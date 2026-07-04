"""The OpenWA (WhatsApp) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp.web import Request, Response

from homeassistant.components import persistent_notification, webhook
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .api import OpenWaClient, OpenWaError
from .const import (
    ATTR_ENTRY_ID,
    ATTR_MESSAGE,
    ATTR_TO,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_SESSION_ID,
    CONF_WEBHOOK_ID,
    DATA_CLIENT,
    DATA_OW_WEBHOOK_ID,
    DOMAIN,
    EVENT_MESSAGE,
    OW_EVENT_MESSAGE_RECEIVED,
    SERVICE_SEND_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.NOTIFY]

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TO): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


def normalise_chat_id(to: str) -> str:
    """Turn a phone number or chat id into a WhatsApp chat id."""
    to = to.strip()
    if "@" in to:
        return to
    digits = to.replace(" ", "").lstrip("+")
    return f"{digits}@c.us"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenWA from a config entry."""
    client = OpenWaClient(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_API_KEY],
    )
    session_id = entry.data[CONF_SESSION_ID]

    # Verify the connection is alive so a dead server surfaces as "retry".
    try:
        await client.list_sessions()
    except OpenWaError as err:
        _LOGGER.warning("OpenWA not reachable during setup: %s", err)
        raise ConfigEntryNotReady(str(err)) from err

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = {
        DATA_CLIENT: client,
        CONF_SESSION_ID: session_id,
        DATA_OW_WEBHOOK_ID: None,
    }

    await _async_setup_incoming(hass, entry, client, session_id)

    _async_register_service(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_setup_incoming(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: OpenWaClient,
    session_id: str,
) -> None:
    """Register the HA webhook and subscribe OpenWA to it."""
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = webhook.async_generate_id()
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: webhook_id}
        )

    webhook.async_register(
        hass,
        DOMAIN,
        "OpenWA WhatsApp",
        webhook_id,
        _make_webhook_handler(entry.entry_id),
        local_only=True,
    )
    entry.async_on_unload(
        lambda: webhook.async_unregister(hass, webhook_id)
    )

    # Build the URL OpenWA should POST to (prefer the internal LAN URL).
    try:
        base = get_url(
            hass, allow_external=False, allow_ip=True, prefer_external=False
        )
    except NoURLAvailableError:
        try:
            base = get_url(hass, allow_ip=True)
        except NoURLAvailableError:
            _LOGGER.warning(
                "No Home Assistant URL available; incoming WhatsApp events "
                "disabled. Set an internal URL under Settings > Network"
            )
            return
    target_url = f"{base}/api/webhook/{webhook_id}"

    # Clean up any previous subscription that points at this HA webhook.
    try:
        for hook in await client.list_webhooks(session_id):
            if hook.get("url", "").endswith(f"/api/webhook/{webhook_id}"):
                await client.delete_webhook(session_id, hook["id"])
    except OpenWaError as err:
        _LOGGER.debug("Could not list/clean existing webhooks: %s", err)

    try:
        created = await client.create_webhook(
            session_id, target_url, [OW_EVENT_MESSAGE_RECEIVED]
        )
    except OpenWaError as err:
        msg = str(err)
        _LOGGER.error("Could not register OpenWA webhook (%s)", msg)
        if "not allowed" in msg.lower():
            _async_ssrf_notification(hass, base)
        return

    hass.data[DOMAIN][entry.entry_id][DATA_OW_WEBHOOK_ID] = created.get("id")

    async def _remove_ow_webhook() -> None:
        hook_id = hass.data[DOMAIN][entry.entry_id][DATA_OW_WEBHOOK_ID]
        if hook_id:
            try:
                await client.delete_webhook(session_id, hook_id)
            except OpenWaError as err:
                _LOGGER.debug("Could not delete OpenWA webhook: %s", err)

    entry.async_on_unload(
        lambda: hass.async_create_task(_remove_ow_webhook())
    )


@callback
def _async_ssrf_notification(hass: HomeAssistant, base: str) -> None:
    """Tell the user how to allow the internal webhook target in OpenWA."""
    host = base.split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]
    persistent_notification.async_create(
        hass,
        (
            "OpenWA blocked the webhook to Home Assistant (SSRF protection). "
            f"Add this host to OpenWA's allow-list and restart the container:\n\n"
            f"`SSRF_ALLOWED_HOSTS={host}`\n\n"
            "Then reload the OpenWA integration. Outgoing messages already work."
        ),
        title="OpenWA: allow incoming webhook",
        notification_id="openwa_ssrf",
    )


def _make_webhook_handler(entry_id: str):
    """Return a webhook handler bound to a config entry."""

    async def _handle(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.debug("Ignoring non-JSON webhook payload")
            return None

        data = payload.get("data") or {}
        event_data = {
            "entry_id": entry_id,
            "event": payload.get("event"),
            "session_id": payload.get("sessionId"),
            "timestamp": payload.get("timestamp"),
            "from": data.get("from"),
            "author": data.get("author"),
            "body": data.get("body"),
            "type": data.get("type"),
            "is_group": bool(data.get("isGroup")),
            "from_me": bool(data.get("fromMe")),
            "chat_id": data.get("from"),
            "payload": payload,
        }
        hass.bus.async_fire(EVENT_MESSAGE, event_data)
        return None

    return _handle


@callback
def _async_register_service(hass: HomeAssistant) -> None:
    """Register the send_message service once."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        return

    async def _handle_send(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data.get(ATTR_ENTRY_ID))
        data = hass.data[DOMAIN][entry.entry_id]
        client: OpenWaClient = data[DATA_CLIENT]
        chat_id = normalise_chat_id(call.data[ATTR_TO])
        try:
            await client.send_text(
                data[CONF_SESSION_ID], chat_id, call.data[ATTR_MESSAGE]
            )
        except OpenWaError as err:
            raise HomeAssistantError(f"Sending WhatsApp message failed: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, _handle_send, schema=SEND_MESSAGE_SCHEMA
    )


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """Find the config entry to use for a service call."""
    loaded = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state == ConfigEntryState.LOADED
    ]
    if entry_id:
        for entry in loaded:
            if entry.entry_id == entry_id:
                return entry
        raise HomeAssistantError(f"OpenWA account {entry_id} not found or not loaded")
    if not loaded:
        raise HomeAssistantError("No OpenWA account is configured")
    if len(loaded) > 1:
        raise HomeAssistantError(
            "Several OpenWA accounts configured; pass 'entry_id' to choose one"
        )
    return loaded[0]


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Remove the shared service when the last entry goes away.
        if not hass.config_entries.async_entries(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    return unload_ok
