"""Constants for the OpenWA (WhatsApp) integration."""

from __future__ import annotations

DOMAIN = "openwa"

# Config entry keys
CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_SESSION_ID = "session_id"
CONF_SESSION_NAME = "session_name"
CONF_SESSION_PHONE = "session_phone"
CONF_WEBHOOK_ID = "webhook_id"

# Options
CONF_DEFAULT_RECIPIENT = "default_recipient"

# Runtime data stored on hass.data[DOMAIN][entry_id]
DATA_CLIENT = "client"
DATA_OW_WEBHOOK_ID = "ow_webhook_id"
DATA_UNSUB = "unsub"

# Event fired on the HA bus for every received WhatsApp message
EVENT_MESSAGE = "openwa_message"

# OpenWA webhook event we subscribe to (incoming messages)
OW_EVENT_MESSAGE_RECEIVED = "message.received"

# Service
SERVICE_SEND_MESSAGE = "send_message"
ATTR_TO = "to"
ATTR_MESSAGE = "message"
ATTR_ENTRY_ID = "entry_id"

DEFAULT_TIMEOUT = 20
