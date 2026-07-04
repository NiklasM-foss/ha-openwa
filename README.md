# OpenWA (WhatsApp) for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for
[**OpenWA**](https://github.com/rmyndharis/OpenWA), the self-hosted WhatsApp API
gateway. Set it up entirely from the UI (no YAML), send WhatsApp messages from
automations, and receive incoming messages as a Home Assistant event.

> This is an unofficial, community integration and is not affiliated with
> WhatsApp/Meta or the OpenWA project.

## Features

- **GUI setup** (config flow): enter the OpenWA URL + API key, pick your linked
  WhatsApp session. No `configuration.yaml`.
- **Send messages**: the `openwa.send_message` service (and an optional
  `notify` entity for a fixed recipient).
- **Receive messages**: every incoming WhatsApp message fires the
  **`openwa_message`** event on the Home Assistant bus. The integration
  registers a Home Assistant webhook and subscribes OpenWA to it automatically.

## Requirements

- A running **OpenWA** server (v that exposes `/api/sessions`, the EASY dashboard
  build) reachable from Home Assistant.
- At least one **linked WhatsApp session** in OpenWA (scan the QR in the OpenWA
  dashboard first).
- An **API key** (the OpenWA API master key or a key created in the dashboard).
- For **incoming** messages, OpenWA must be allowed to call back into Home
  Assistant. OpenWA blocks internal/LAN targets by default (SSRF protection), so
  add your HA host to its allow-list and restart the OpenWA container:

  ```env
  SSRF_ALLOWED_HOSTS=<home-assistant-ip>
  ```

  Outgoing messages work without this.

## Installation (HACS)

1. HACS → three-dot menu → **Custom repositories**.
2. Add `https://github.com/NiklasM-foss/ha-openwa` with category
   **Integration**.
3. Install **OpenWA (WhatsApp)**, then restart Home Assistant.
4. Settings → Devices & Services → **Add Integration** → search **OpenWA**.

Manual alternative: copy `custom_components/openwa` into your HA
`config/custom_components/` folder and restart.

## Setup

The config flow asks for:

- **OpenWA URL** – e.g. `http://192.168.1.10:2785`
- **API key** – sent as the `x-api-key` header

It then lists your WhatsApp sessions; pick the one to use. Done.

## Sending messages

Service **`openwa.send_message`**:

```yaml
action: openwa.send_message
data:
  to: "4915233535738"        # international, no "+"  — or a full chat id
  message: "Hello from Home Assistant"
```

`to` accepts a phone number in international format without `+`, or a full chat
id (`12345@c.us` for a contact, `12345@g.us` for a group).

Optionally set a **default recipient** in the integration's options to get a
`notify.<name>` entity that always sends to that number:

```yaml
action: notify.send_message
target:
  entity_id: notify.openwa_whatsapp
data:
  message: "Ping"
```

## Receiving messages — the `openwa_message` event

Every incoming message fires `openwa_message` with this data:

| Field          | Meaning                                             |
|----------------|-----------------------------------------------------|
| `from`         | Sender chat id (`…@c.us`, group `…@g.us`)            |
| `author`       | Real sender inside a group (empty for direct chats) |
| `body`         | Message text                                        |
| `type`         | `text`, `image`, `audio`, …                         |
| `is_group`     | Whether it came from a group                        |
| `from_me`      | Whether it was sent by your own number              |
| `chat_id`      | Same as `from` (convenience for replies)            |
| `session_id`   | OpenWA session id                                   |
| `timestamp`    | ISO timestamp                                       |
| `payload`      | The full raw OpenWA payload                         |

Example — reply to a keyword:

```yaml
alias: WhatsApp status command
triggers:
  - trigger: event
    event_type: openwa_message
conditions:
  - "{{ not trigger.event.data.from_me }}"
  - "{{ trigger.event.data.body | lower == 'status' }}"
actions:
  - action: openwa.send_message
    data:
      to: "{{ trigger.event.data.chat_id }}"
      message: "House is {{ states('climate.living_room') }}."
```

## Notes

- The integration binds to one WhatsApp **session id**. If you delete and
  re-link the session in OpenWA, remove and re-add the integration (or it will
  point at the old session).
- Incoming delivery uses a Home Assistant webhook with `local_only`, so OpenWA
  must reach HA over the local network.

## License

[MIT](LICENSE)
