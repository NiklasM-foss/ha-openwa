"""Connectivity of the OpenWA WhatsApp session."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN, STATUS_READY
from .coordinator import OpenWaCoordinator
from .entity import OpenWaSessionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connectivity binary sensor."""
    coordinator: OpenWaCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities([OpenWaConnectionSensor(coordinator, entry)])


class OpenWaConnectionSensor(OpenWaSessionEntity, BinarySensorEntity):
    """On while the session is linked and able to send.

    Anything other than "ready" (disconnected, initializing, a QR scan
    pending) means messages are refused with HTTP 400, so this is the entity
    to alert on.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connection"

    def __init__(self, coordinator: OpenWaCoordinator, entry: ConfigEntry) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, "connection")

    @property
    def is_on(self) -> bool:
        """Return True while the session is ready."""
        return self.session.get("status") == STATUS_READY

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose why the session is not ready."""
        return {
            "status": self.session.get("status"),
            "last_error": self.session.get("lastError"),
        }
