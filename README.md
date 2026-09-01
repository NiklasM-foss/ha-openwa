# OpenWA (WhatsApp) for Home Assistant

*Deutsche Version: [README.de.md](README.de.md)*

A custom [Home Assistant](https://www.home-assistant.io/) integration for
[**OpenWA**](https://github.com/rmyndharis/OpenWA), the self-hosted WhatsApp API
gateway. Set it up entirely from the UI, send WhatsApp messages from
automations, receive incoming messages as a Home Assistant event, and watch the
state of the linked WhatsApp session.

> Unofficial community integration. Not affiliated with WhatsApp/Meta or with
> the OpenWA project.

## Features

- **GUI setup** (config flow): enter the OpenWA URL and an API key, then pick
  the linked WhatsApp session. No `configuration.yaml`.
- **Send messages** with the `openwa.send_message` service, plus an optional
  `notify` entity for one fixed recipient.
- **Receive messages**: every incoming message fires the `openwa_message` event
  on the Home Assistant bus. The integration registers a Home Assistant webhook
  and subscribes OpenWA to it automatically.
- **Session monitoring**: connectivity, status, phone number, display name,
  timestamps and the last error of the session as entities, so a dropped link
  is visible instead of silently swallowing messages.

## Requirements

- Home Assistant **2026.3** or newer.
- A running **OpenWA** server reachable from Home Assistant. The integration
  uses its REST API (`/api/sessions`, `/api/sessions/<id>/messages/send-text`,
  `/api/sessions/<id>/webhooks`).
- At least one **linked WhatsApp session** in OpenWA (scan the QR code in the
  OpenWA dashboard first).
- An **API key**: the OpenWA API master key, or a key created in the dashboard.
  It is sent as the `x-api-key` header.
- For **incoming** messages, OpenWA must be able to call back into Home
  Assistant. OpenWA blocks internal/LAN targets by default (SSRF protection),
  so add the Home Assistant host to its allow-list and restart the OpenWA
  container:

  ```env
  SSRF_ALLOWED_HOSTS=<home-assistant-ip>
  ```

  Outgoing messages work without this.

## Installation (HACS)

1. HACS, three-dot menu, **Custom repositories**.
2. Add `https://github.com/NiklasM-foss/ha-openwa` with category
   **Integration**.
3. Install **OpenWA (WhatsApp)**, then restart Home Assistant.
4. Settings, Devices & Services, **Add Integration**, search for **OpenWA**.

Manual alternative: copy the `custom_components/openwa` folder into your Home
Assistant `config/custom_components/` directory and restart.

## Configuration

The config flow asks for:

- **OpenWA URL**, for example `http://192.168.1.10:2785`. A missing `http://`
  is added automatically and a trailing slash is removed.
- **API key**, sent as the `x-api-key` header.

The integration then reads the sessions from the server. With exactly one
session it is used directly; with several you get a second step to choose one.
A config entry is bound to one URL plus session id, so the same session cannot
be added twice, while several OpenWA accounts can be added side by side.

### Options

The integration options offer a single setting:

- **Default recipient**: a phone number in international format without `+`
  (for example `4915233535738`) or a full chat id. Setting it creates a
  `notify` entity that always sends to that recipient; leaving it empty removes
  the entity again. Changing the option reloads the config entry, so it takes
  effect right away.

## Sending messages

Service **`openwa.send_message`**:

```yaml
action: openwa.send_message
data:
  to: "4915233535738"        # international format, no "+", or a full chat id
  message: "Hello from Home Assistant"
```

| Field      | Required | Meaning                                                                   |
|------------|----------|---------------------------------------------------------------------------|
| `to`       | yes      | Phone number without `+`, or a chat id (`12345@c.us`, group `12345@g.us`)  |
| `message`  | yes      | The text to send                                                          |
| `entry_id` | no       | Which OpenWA account to use; only needed with more than one config entry   |

A plain number is turned into `<digits>@c.us` automatically, while anything
that already contains `@` is passed through unchanged. If the message cannot be
delivered, the service call raises an error instead of failing silently.

With a default recipient configured, the notify entity can be used instead:

```yaml
action: notify.send_message
target:
  entity_id: notify.<device>_whatsapp
data:
  message: "Ping"
```

If a `title` is given, it is placed on its own line in front of the message.

## Receiving messages: the `openwa_message` event

The integration registers a local-only Home Assistant webhook and subscribes
OpenWA's `message.received` event to it. Every incoming message fires
`openwa_message` on the Home Assistant bus with this data:

| Field        | Meaning                                                    |
|--------------|------------------------------------------------------------|
| `from`       | Sender chat id (`...@c.us`, group `...@g.us`)               |
| `author`     | Real sender inside a group, not set for direct chats        |
| `body`       | Message text                                               |
| `type`       | Message type as reported by OpenWA, for example `text`     |
| `is_group`   | Whether the message came from a group                      |
| `from_me`    | Whether it was sent by your own number                     |
| `chat_id`    | Same as `from`, convenient for replies                     |
| `session_id` | OpenWA session id                                          |
| `event`      | The OpenWA event name                                      |
| `timestamp`  | Timestamp as sent by OpenWA                                |
| `entry_id`   | Config entry that received the message                     |
| `payload`    | The complete raw OpenWA payload                            |

`from` is a Jinja keyword, so use the subscript form
`trigger.event.data['from']` in templates.

Example, reply to a keyword:

```yaml
alias: WhatsApp status command
triggers:
  - trigger: event
    event_type: openwa_message
conditions:
  - "{{ not trigger.event.data.from_me }}"
  - "{{ trigger.event.data.body | default('') | lower == 'status' }}"
actions:
  - action: openwa.send_message
    data:
      to: "{{ trigger.event.data.chat_id }}"
      message: "House is {{ states('climate.living_room') }}."
```

## Session entities

The integration polls `/api/sessions` every 30 seconds and exposes the record
of the session it is bound to. All entities belong to one device named after
the config entry.

| Entity                            | Type         | Meaning                                                                                      |
|-----------------------------------|--------------|----------------------------------------------------------------------------------------------|
| `binary_sensor.<name>_connection` | connectivity | **On** while the session status is `ready`. Carries `status` and `last_error` as attributes.  |
| `sensor.<name>_session_status`    | text         | Raw status string from OpenWA. Carries `session_id` and `session_name` as attributes.        |
| `sensor.<name>_phone_number`      | text         | The linked number. Diagnostic.                                                               |
| `sensor.<name>_display_name`      | text         | WhatsApp display name of the linked account. Diagnostic.                                     |
| `sensor.<name>_connected_since`   | timestamp    | When the current link came up.                                                               |
| `sensor.<name>_last_activity`     | timestamp    | Last activity on the session.                                                                |
| `sensor.<name>_session_created`   | timestamp    | When the session was created in OpenWA. Diagnostic, disabled by default.                     |
| `sensor.<name>_session_updated`   | timestamp    | Last change to the session record. Diagnostic, disabled by default.                          |
| `sensor.<name>_last_error`        | text         | Last error OpenWA recorded, `unknown` when there is none. Diagnostic.                        |

A session can leave the `ready` state on its own, for example when the phone
stays offline too long or WhatsApp logs the device out. Sending then fails, and
that is easy to miss if nothing watches for it. An automation on the
connectivity sensor closes the gap:

```yaml
automation:
  - alias: WhatsApp gateway disconnected
    triggers:
      - trigger: state
        entity_id: binary_sensor.whatsapp_connection
        to: "off"
        for: "00:05:00"
    actions:
      - action: persistent_notification.create
        data:
          title: WhatsApp gateway down
          message: >-
            Session status: {{ state_attr('binary_sensor.whatsapp_connection',
            'status') }}. Restart it in the OpenWA dashboard.
```

## Troubleshooting

- **"Failed to connect" during setup**: wrong URL or port, or the OpenWA server
  is not reachable from Home Assistant. Requests give up after 20 seconds.
- **"Invalid API key"**: OpenWA answered with HTTP 401 or 403. Check the key,
  and that it is valid for the API and not only for the dashboard UI.
- **"No WhatsApp session found"**: link a device in the OpenWA dashboard first,
  then run the setup again.
- **No incoming messages plus a notification about the webhook**: OpenWA
  refused to register the callback because of its SSRF protection. Put the Home
  Assistant host into `SSRF_ALLOWED_HOSTS`, restart the OpenWA container and
  reload the integration.
- **No incoming messages plus a log warning about a missing URL**: Home
  Assistant could not work out a callback address. Set an internal URL under
  Settings, System, Network, then reload the integration.
- **Entities go unavailable**: the session is no longer listed by
  `/api/sessions`, usually because it was deleted in the OpenWA dashboard, or
  the server cannot be reached.
- **The session was deleted and re-linked**: a config entry is tied to one
  session id. Remove the integration and add it again, otherwise it keeps
  pointing at the old session.
- **The webhook is registered local-only**, so OpenWA has to reach Home
  Assistant over the local network.

## License

[MIT](LICENSE)
