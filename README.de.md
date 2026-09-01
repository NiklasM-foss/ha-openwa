# OpenWA (WhatsApp) für Home Assistant

*English version: [README.md](README.md)*

Eine Custom-Integration für [Home Assistant](https://www.home-assistant.io/),
die [**OpenWA**](https://github.com/rmyndharis/OpenWA) anbindet, das
selbst gehostete WhatsApp-API-Gateway. Einrichtung komplett über die
Oberfläche, WhatsApp-Nachrichten aus Automationen senden, eingehende
Nachrichten als Home-Assistant-Event empfangen und den Zustand der verknüpften
WhatsApp-Sitzung überwachen.

> Inoffizielle Community-Integration. Weder mit WhatsApp/Meta noch mit dem
> OpenWA-Projekt verbunden.

## Funktionen

- **Einrichtung über die Oberfläche** (Config Flow): OpenWA-URL und API-Key
  eingeben, danach die verknüpfte WhatsApp-Sitzung auswählen. Kein
  `configuration.yaml`.
- **Nachrichten senden** über den Dienst `openwa.send_message`, dazu optional
  eine `notify`-Entität für einen festen Empfänger.
- **Nachrichten empfangen**: jede eingehende Nachricht löst das Event
  `openwa_message` auf dem Home-Assistant-Bus aus. Die Integration registriert
  einen Home-Assistant-Webhook und meldet OpenWA automatisch darauf an.
- **Sitzungsüberwachung**: Verbindung, Status, Rufnummer, Anzeigename,
  Zeitstempel und letzter Fehler der Sitzung als Entitäten. So fällt eine
  abgerissene Verknüpfung auf, statt Nachrichten still zu verschlucken.

## Voraussetzungen

- Home Assistant **2026.3** oder neuer.
- Ein laufender **OpenWA-Server**, der von Home Assistant aus erreichbar ist.
  Die Integration nutzt dessen REST-API (`/api/sessions`,
  `/api/sessions/<id>/messages/send-text`, `/api/sessions/<id>/webhooks`).
- Mindestens eine **verknüpfte WhatsApp-Sitzung** in OpenWA (zuerst den
  QR-Code im OpenWA-Dashboard scannen).
- Ein **API-Key**: der API-Master-Key von OpenWA oder ein im Dashboard
  angelegter Key. Er wird als Header `x-api-key` gesendet.
- Für **eingehende** Nachrichten muss OpenWA Home Assistant zurückrufen können.
  OpenWA blockiert interne Ziele im LAN standardmäßig (SSRF-Schutz). Deshalb
  den Home-Assistant-Host in die Allow-List eintragen und den OpenWA-Container
  neu starten:

  ```env
  SSRF_ALLOWED_HOSTS=<home-assistant-ip>
  ```

  Ausgehende Nachrichten funktionieren auch ohne diesen Eintrag.

## Installation (HACS)

1. HACS, Drei-Punkte-Menü, **Benutzerdefinierte Repositories**.
2. `https://github.com/NiklasM-foss/ha-openwa` mit der Kategorie
   **Integration** hinzufügen.
3. **OpenWA (WhatsApp)** installieren und Home Assistant neu starten.
4. Einstellungen, Geräte & Dienste, **Integration hinzufügen**, nach **OpenWA**
   suchen.

Alternativ von Hand: den Ordner `custom_components/openwa` in das
Home-Assistant-Verzeichnis `config/custom_components/` kopieren und neu
starten.

## Konfiguration

Der Config Flow fragt nach:

- **OpenWA-URL**, zum Beispiel `http://192.168.1.10:2785`. Ein fehlendes
  `http://` wird ergänzt, ein Schrägstrich am Ende entfernt.
- **API-Key**, wird als Header `x-api-key` gesendet.

Danach liest die Integration die Sitzungen vom Server. Bei genau einer Sitzung
wird diese direkt genommen, bei mehreren erscheint ein zweiter Schritt zur
Auswahl. Ein Eintrag ist an eine URL plus Sitzungs-ID gebunden, dieselbe
Sitzung lässt sich also nicht zweimal anlegen, mehrere OpenWA-Konten dagegen
schon.

### Optionen

Die Optionen der Integration haben eine einzige Einstellung:

- **Standard-Empfänger**: eine Rufnummer im internationalen Format ohne `+`
  (zum Beispiel `4915233535738`) oder eine vollständige Chat-ID. Ist sie
  gesetzt, entsteht eine `notify`-Entität, die immer an diesen Empfänger
  sendet. Leer lassen entfernt die Entität wieder. Eine Änderung lädt den
  Eintrag neu und wirkt damit sofort.

## Nachrichten senden

Dienst **`openwa.send_message`**:

```yaml
action: openwa.send_message
data:
  to: "4915233535738"        # international ohne "+", oder eine volle Chat-ID
  message: "Hallo aus Home Assistant"
```

| Feld       | Pflicht | Bedeutung                                                                       |
|------------|---------|---------------------------------------------------------------------------------|
| `to`       | ja      | Rufnummer ohne `+` oder Chat-ID (`12345@c.us`, Gruppe `12345@g.us`)              |
| `message`  | ja      | Der zu sendende Text                                                            |
| `entry_id` | nein    | Welches OpenWA-Konto genutzt wird, nur nötig bei mehr als einem Eintrag          |

Eine reine Nummer wird automatisch zu `<ziffern>@c.us`, alles mit einem `@`
bleibt unverändert. Lässt sich die Nachricht nicht zustellen, schlägt der
Dienstaufruf mit einem Fehler fehl, statt still zu scheitern.

Mit einem Standard-Empfänger kann stattdessen die notify-Entität genutzt
werden:

```yaml
action: notify.send_message
target:
  entity_id: notify.<geraet>_whatsapp
data:
  message: "Ping"
```

Ein übergebener `title` wird in einer eigenen Zeile vor die Nachricht gesetzt.

## Nachrichten empfangen: das Event `openwa_message`

Die Integration registriert einen nur lokal erreichbaren
Home-Assistant-Webhook und abonniert darauf das OpenWA-Event
`message.received`. Jede eingehende Nachricht löst `openwa_message` auf dem
Home-Assistant-Bus mit diesen Daten aus:

| Feld         | Bedeutung                                                    |
|--------------|--------------------------------------------------------------|
| `from`       | Chat-ID des Absenders (`...@c.us`, Gruppe `...@g.us`)         |
| `author`     | Tatsächlicher Absender in einer Gruppe, bei Einzelchats leer  |
| `body`       | Text der Nachricht                                           |
| `type`       | Nachrichtentyp laut OpenWA, zum Beispiel `text`              |
| `is_group`   | Ob die Nachricht aus einer Gruppe kam                        |
| `from_me`    | Ob sie von der eigenen Nummer gesendet wurde                 |
| `chat_id`    | Wie `from`, praktisch für Antworten                          |
| `session_id` | Sitzungs-ID in OpenWA                                        |
| `event`      | Name des OpenWA-Events                                       |
| `timestamp`  | Zeitstempel, so wie OpenWA ihn sendet                        |
| `entry_id`   | Eintrag, der die Nachricht empfangen hat                     |
| `payload`    | Die komplette rohe OpenWA-Nutzlast                           |

`from` ist ein Jinja-Schlüsselwort, in Templates deshalb die Schreibweise
`trigger.event.data['from']` verwenden.

Beispiel, Antwort auf ein Stichwort:

```yaml
alias: WhatsApp Statusabfrage
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
      message: "Wohnzimmer: {{ states('climate.wohnzimmer') }}."
```

## Entitäten der Sitzung

Die Integration fragt `/api/sessions` alle 30 Sekunden ab und stellt den
Datensatz der gebundenen Sitzung bereit. Alle Entitäten gehören zu einem Gerät,
das nach dem Eintrag benannt ist.

| Entität                            | Typ           | Bedeutung                                                                                       |
|------------------------------------|---------------|-------------------------------------------------------------------------------------------------|
| `binary_sensor.<name>_connection`  | Verbindung    | **An**, solange der Status `ready` ist. Attribute `status` und `last_error`.                     |
| `sensor.<name>_session_status`     | Text          | Roher Status von OpenWA. Attribute `session_id` und `session_name`.                              |
| `sensor.<name>_phone_number`       | Text          | Die verknüpfte Nummer. Diagnose.                                                                 |
| `sensor.<name>_display_name`       | Text          | WhatsApp-Anzeigename des verknüpften Kontos. Diagnose.                                            |
| `sensor.<name>_connected_since`    | Zeitstempel   | Seit wann die aktuelle Verknüpfung steht.                                                        |
| `sensor.<name>_last_activity`      | Zeitstempel   | Letzte Aktivität auf der Sitzung.                                                                |
| `sensor.<name>_session_created`    | Zeitstempel   | Anlage der Sitzung in OpenWA. Diagnose, standardmäßig deaktiviert.                                |
| `sensor.<name>_session_updated`    | Zeitstempel   | Letzte Änderung am Sitzungsdatensatz. Diagnose, standardmäßig deaktiviert.                        |
| `sensor.<name>_last_error`         | Text          | Letzter von OpenWA vermerkter Fehler, `unknown`, wenn es keinen gibt. Diagnose.                    |

Eine Sitzung kann den Zustand `ready` von selbst verlassen, etwa wenn das
Telefon zu lange offline ist oder WhatsApp das Gerät abmeldet. Senden schlägt
dann fehl, und das fällt leicht durch, wenn niemand darauf achtet. Eine
Automation auf dem Verbindungssensor schließt die Lücke:

```yaml
automation:
  - alias: WhatsApp-Gateway getrennt
    triggers:
      - trigger: state
        entity_id: binary_sensor.whatsapp_connection
        to: "off"
        for: "00:05:00"
    actions:
      - action: persistent_notification.create
        data:
          title: WhatsApp-Gateway ausgefallen
          message: >-
            Status der Sitzung: {{
            state_attr('binary_sensor.whatsapp_connection', 'status') }}. Im
            OpenWA-Dashboard neu starten.
```

## Fehlersuche

- **"Verbindung fehlgeschlagen" bei der Einrichtung**: URL oder Port stimmen
  nicht, oder der OpenWA-Server ist von Home Assistant aus nicht erreichbar.
  Anfragen brechen nach 20 Sekunden ab.
- **"Ungültiger API-Key"**: OpenWA hat mit HTTP 401 oder 403 geantwortet. Key
  prüfen und sicherstellen, dass er für die API gilt und nicht nur für die
  Oberfläche des Dashboards.
- **"Keine WhatsApp-Sitzung gefunden"**: zuerst im OpenWA-Dashboard ein Gerät
  verknüpfen, danach die Einrichtung erneut starten.
- **Keine eingehenden Nachrichten, dazu eine Meldung zum Webhook**: OpenWA hat
  die Registrierung wegen seines SSRF-Schutzes abgelehnt. Den
  Home-Assistant-Host in `SSRF_ALLOWED_HOSTS` eintragen, den OpenWA-Container
  neu starten und die Integration neu laden.
- **Keine eingehenden Nachrichten, dazu eine Warnung über eine fehlende URL im
  Log**: Home Assistant konnte keine Rückruf-Adresse ermitteln. Unter
  Einstellungen, System, Netzwerk eine interne URL setzen und die Integration
  neu laden.
- **Entitäten werden nicht verfügbar**: die Sitzung steht nicht mehr in
  `/api/sessions`, meist weil sie im OpenWA-Dashboard gelöscht wurde, oder der
  Server ist nicht erreichbar.
- **Sitzung gelöscht und neu verknüpft**: ein Eintrag hängt an genau einer
  Sitzungs-ID. Die Integration entfernen und neu hinzufügen, sonst zeigt sie
  weiter auf die alte Sitzung.
- **Der Webhook ist nur lokal erreichbar**, OpenWA muss Home Assistant also
  über das lokale Netz erreichen können.

## Lizenz

[MIT](LICENSE)
