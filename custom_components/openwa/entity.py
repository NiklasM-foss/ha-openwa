"""Shared base class for entities that describe the WhatsApp session."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenWaCoordinator


class OpenWaSessionEntity(CoordinatorEntity[OpenWaCoordinator]):
    """Base entity bound to the session record of one config entry."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OpenWaCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenWA",
        )

    @property
    def session(self) -> dict[str, Any]:
        """Return the current session record."""
        return self.coordinator.data or {}
