# Tasklane über API und Remote-MCP verwenden

Melde dich auf deiner Tasklane-Domain an und öffne **Dashboard → API & MCP**. Erstelle einen persönlichen Schlüssel mit Name, Ablaufzeit (1–365 Tage, standardmäßig 90), Rechtestufe und optional einer Begrenzung auf einen Workspace. Sichere den einmal angezeigten Wert im Secret-Speicher deiner verbundenen Anwendung. Die Liste zeigt den Schlüssel nicht erneut. **Widerrufen** beendet dessen Nutzung sofort.

## Rechte und Identität

- `read`: Projekte, Tickets, Kommentare, Dateien und Berichte lesen.
- `write`: zusätzlich Tickets, Kommentare, Checklisten, Dateien und eigene Zeitbuchungen bearbeiten.
- `manage`: zusätzlich Workspace-Mitglieder, Projektfreigaben und Importverbindungen verwalten.

Keine Stufe verleiht zusätzliche Projekt- oder Leitungsrechte. Alle Aufrufe verwenden das Konto der ausstellenden Person und prüfen dessen Aktivität, Mitgliedschaft, Ablauf und Widerruf erneut. Eine Workspace-Begrenzung gilt auch für Projektlisten, Zeitberichte und Dateizugriffe. Schlüssel sind an die konfigurierte öffentliche Domain gebunden; bei einem Domainwechsel neue Schlüssel ausstellen.

Browser-Sitzungen reichen für die Integrations-API nicht aus. Sende immer `Authorization: Bearer …`. Verwende HTTPS außerhalb der lokalen Entwicklung. Sende Schlüssel niemals als URL-Parameter und speichere sie nicht in `localStorage` oder `sessionStorage`. Die Erstellung und Verwaltung von Schlüsseln selbst erfolgt ausschließlich über die angemeldete, CSRF-geschützte Oberfläche.

## Versionierte HTTP-API

Die Endpunkte haben **keinen abschließenden Schrägstrich**:

| Methode | Pfad | Inhalt |
| --- | --- | --- |
| GET | `/api/v1/openapi.json` | Öffentliche OpenAPI-3.1-Beschreibung der Aktionen |
| GET | `/api/v1/actions` | Für diesen Schlüssel freigegebene Aktionen und Eingabeschemata |
| POST | `/api/v1/actions/<aktion>` | Aktion mit JSON-Argumenten ausführen |
| GET | `/api/v1/workspaces` | Zugängliche Workspaces |
| GET | `/api/v1/projects` | Projekte, optional `?workspace_id=123` |
| GET | `/api/v1/projects/<id>` | Projektdaten und Ticketübersicht |
| GET | `/api/v1/projects/<id>/tickets/<ticket_id>` | Ein Ticket |
| GET | `/api/v1/projects/<id>/attachments/<uuid>/content` | Privater Dateidownload |

Schreibaufrufe erhalten ein **direktes Argumentobjekt**. Die Antwort enthält das Ergebnis unter `result`. Beispiel mit einem zuvor sicher gesetzten `TASKLANE_API_TOKEN`:

```bash
curl --fail-with-body 'https://tasks.example.com/api/v1/projects' \
  -H "Authorization: Bearer $TASKLANE_API_TOKEN"

curl --fail-with-body 'https://tasks.example.com/api/v1/actions/create_ticket' \
  -H "Authorization: Bearer $TASKLANE_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"project_id":123,"title":"API-Anbindung testen","custom_fields":{"kundenreferenz":"REF-42"}}'
```

IDs aus den aktuellen Antworten lesen. `get_project` enthält Status, Mitglieder, Tags und Felddefinitionen. Updates von Kommentaren, Checklisten, Ticket- und Zeitdaten unterstützen nach jeweiligem Eingabeschema `expected_updated_at` als Schutz vor konkurrierenden Änderungen. `assignee_ids` und `tag_ids` ersetzen die entsprechende Liste. Nicht übergebene Werte bleiben bei Updates erhalten. `custom_fields` verwendet stabile Feldschlüssel.

Fehler enthalten `error`: `400` ungültige Eingabe, `401` fehlender/ungültiger Schlüssel, `403` unzureichende Rechte, `404` fehlende oder unzugängliche Ressource, `409` Änderungskonflikt, `413` zu großer Inhalt. Browser-Origins werden gesondert geprüft; zusätzliche vertrauenswürdige Origins können serverseitig über `INTEGRATION_ALLOWED_ORIGINS` konfiguriert werden. Die API ist für Serverintegration ausgelegt und liefert keine allgemeine CORS-Freigabe.

## Remote-MCP

Endpoint: `https://tasks.example.com/mcp`. Transport: **Streamable HTTP**, stateless, JSON-Antworten. Konfiguriere den persönlichen Schlüssel als `Authorization: Bearer …` in deinem MCP-Client. Die konkrete Konfigurationsdatei hängt vom Client ab. Es gibt 63 Werkzeuge; `read`-Schlüssel sehen nur lesende Werkzeuge. Die Fachlogik und Rechte sind mit API und Oberfläche identisch.

Dieser Server verwendet persönliche Bearer-Schlüssel. Eine automatische OAuth-Anmeldung bzw. dynamische Clientregistrierung wird nicht angeboten. Der Client muss konfigurierbare Authorization-Header unterstützen. Anmeldedaten bleiben beim Client im jeweiligen Secret-Speicher.

Lokal steht weiterhin der stdio-Server zur Verfügung: `make mcp-config MCP_EMAIL=you@example.com` und `make mcp-check MCP_EMAIL=you@example.com`. Er benötigt einen vertrauenswürdigen lokalen Prozess mit Datenbankzugriff. Die E-Mail-Auswahl ist kein öffentlicher Anmeldeweg.

## Dateien über API oder MCP

Die chunkbasierten Aktionen übertragen echte Dateiinhalte und verwenden dieselben privaten Anhänge wie die Oberfläche:

1. `start_attachment_upload`: `project_id`, `ticket_id`, `filename`, `size`, optional `content_type`, `sha256`, `comment_id` angeben. Die Antwort enthält die UUID und den nächsten Offset.
2. `put_attachment_chunk`: `project_id`, `attachment_id`, `offset`, `data_base64`. Pro Chunk höchstens **65536 Rohbytes**, Base64 kodiert. Offsets müssen exakt fortlaufend sein.
3. `get_attachment_upload` nach einer Unterbrechung aufrufen und ab dem gemeldeten Offset fortsetzen.
4. `complete_attachment_upload`: Vollständigkeit und ggf. die vorher angegebene SHA-256-Prüfsumme prüfen lassen. Erst danach ist die Datei verfügbar.
5. Alternativ mit `cancel_attachment_upload` abbrechen.

`read_attachment_chunk` liefert Base64-Inhalt, `next_offset`, Prüfsumme und `eof`; weiter lesen, bis `eof` wahr ist. Die API bietet außerdem den binären Downloadendpunkt. `delete_attachment` erfordert Autorenschaft oder Projekt-/Workspace-Leitung. Standardlimits: 50 MiB je Datei, 1 GiB je Ticket; unvollständige Uploads laufen nach 24 Stunden ab.

Kommentare: `list_comments`, `create_comment`, `update_comment`, `delete_comment`. Checklisten: `list_checklists`, `create_checklist`, `update_checklist`, `delete_checklist`, `create_checklist_item`, `update_checklist_item`, `delete_checklist_item`. Felder: `list_custom_fields`, `create_custom_field`, `update_custom_field`. Verlauf: `list_activity`. Listen mit `offset` und `limit` bis zum gemeldeten Gesamtumfang durchlaufen, statt nur die erste Seite zu übernehmen.
