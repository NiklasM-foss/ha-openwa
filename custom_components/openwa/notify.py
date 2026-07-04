"""Notify entity for OpenWA (sends to a configured default recipient)."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import normalise_chat_id
from .api import OpenWaClient, OpenWaError
from .const import (
    CONF_DEFAULT_RECIPIENT,
    CONF_SESSION_ID,
    DATA_CLIENT,
    DOMAIN,
)
from homeassistant.exceptions import HomeAssistantError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the notify entity if a default recipient is configured."""
    recipient = (entry.options.get(CONF_DEFAULT_RECIPIENT) or "").strip()
    if not recipient:
        return
    async_add_entities([OpenWaNotifyEntity(entry, recipient)])


class OpenWaNotifyEntity(NotifyEntity):
    """A notify entity that sends WhatsApp messages to a fixed recipient."""

    _attr_has_entity_name = True
    _attr_name = "WhatsApp"

    def __init__(self, entry: ConfigEntry, recipient: str) -> None:
        """Initialise the entity."""
        self._entry = entry
        self._recipient = recipient
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenWA",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the configured recipient."""
        data = self.hass.data[DOMAIN][self._entry.entry_id]
        client: OpenWaClient = data[DATA_CLIENT]
        chat_id = normalise_chat_id(self._recipient)
        body = f"{title}\n{message}" if title else message
        try:
            await client.send_text(data[CONF_SESSION_ID], chat_id, body)
        except OpenWaError as err:
            raise HomeAssistantError(
                f"Sending WhatsApp message failed: {err}"
            ) from err
