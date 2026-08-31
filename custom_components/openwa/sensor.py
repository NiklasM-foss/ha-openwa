"""Sensors describing the OpenWA WhatsApp session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import OpenWaCoordinator
from .entity import OpenWaSessionEntity


def _text(key: str) -> Callable[[dict[str, Any]], str | None]:
    """Return a getter for a plain string field."""

    def _get(session: dict[str, Any]) -> str | None:
        value = session.get(key)
        if value is None or value == "":
            return None
        return str(value)

    return _get


def _timestamp(key: str) -> Callable[[dict[str, Any]], datetime | None]:
    """Return a getter that parses an ISO 8601 field into a datetime.

    OpenWA sends UTC with a trailing Z ("2026-08-31T13:48:22.341Z"), which
    dt_util handles, but a server without the suffix would be read as naive
    local time. Anything unparsable becomes None so the entity shows unknown
    rather than breaking the whole platform.
    """

    def _get(session: dict[str, Any]) -> datetime | None:
        raw = session.get(key)
        if not raw:
            return None
        parsed = dt_util.parse_datetime(str(raw))
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
        return parsed

    return _get


@dataclass(frozen=True, kw_only=True)
class OpenWaSensorDescription(SensorEntityDescription):
    """Describes an OpenWA session sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[OpenWaSensorDescription, ...] = (
    OpenWaSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:whatsapp",
        value_fn=_text("status"),
    ),
    OpenWaSensorDescription(
        key="phone",
        translation_key="phone",
        icon="mdi:phone",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("phone"),
    ),
    OpenWaSensorDescription(
        key="push_name",
        translation_key="push_name",
        icon="mdi:account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("pushName"),
    ),
    OpenWaSensorDescription(
        key="connected_at",
        translation_key="connected_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timestamp("connectedAt"),
    ),
    OpenWaSensorDescription(
        key="last_active",
        translation_key="last_active",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timestamp("lastActive"),
    ),
    OpenWaSensorDescription(
        key="created_at",
        translation_key="created_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_timestamp("createdAt"),
    ),
    OpenWaSensorDescription(
        key="updated_at",
        translation_key="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_timestamp("updatedAt"),
    ),
    OpenWaSensorDescription(
        key="last_error",
        translation_key="last_error",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_text("lastError"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the session sensors."""
    coordinator: OpenWaCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        OpenWaSessionSensor(coordinator, entry, description)
        for description in SENSORS
    )


class OpenWaSessionSensor(OpenWaSessionEntity, SensorEntity):
    """A single field of the session record."""

    entity_description: OpenWaSensorDescription

    def __init__(
        self,
        coordinator: OpenWaCoordinator,
        entry: ConfigEntry,
        description: OpenWaSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the value of this field."""
        return self.entity_description.value_fn(self.session)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the session identity on the status sensor."""
        if self.entity_description.key != "status":
            return None
        return {
            "session_id": self.session.get("id"),
            "session_name": self.session.get("name"),
        }
