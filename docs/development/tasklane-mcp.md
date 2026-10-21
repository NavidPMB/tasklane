# Tasklane entwickeln und per MCP verbinden

## Architektur

`backend/modules/work/` enthält Modelle und die gemeinsame Fachlogik für Projekte, Mitglieder, Status, Tags und Tickets. `services.OPERATIONS` definiert Werkzeugnamen, Eingabeschemata und Handler. HTTP-API und MCP rufen beide `services.execute` auf. Eingaben werden mit JSON Schema validiert; Projektzugriff und fachliche Verknüpfungen werden im Backend geprüft.

`GET /api/work/projects/` liefert nur eigene Projekte. `GET /api/work/projects/<id>/` liefert den aktuellen Projektstand einschließlich geordneter Status, aktiver Mitglieder, Tags und Tickets. Änderungen erfolgen per CSRF-geschütztem `POST /api/work/actions/` mit `{"action": "<Werkzeugname>", "arguments": {...}}`. Die Registry ist die vollständige Referenz der Aktionen. Fachliche Fehler liefern `400`, fehlender Projektzugriff `404`, fehlende Sitzung `401`, unzulässige Verwaltungsaktionen `403` und konkurrierende Ticketänderungen `409`.

Die Projektleitung verwaltet Projektname, Beschreibung und Mitgliedschaft. Mitglieder können Tickets, Status und Tags verwalten. Projektabfragen wenden die Mitgliedschaft vor der Ausgabe an; es gibt keinen globalen Staff-Bypass. Fremde Status, Tags, Eltern-Tickets und Zuständige werden zurückgewiesen. Die Oberfläche bietet keine Benutzerauflistung außerhalb des Projekts an.

Schreibzugriffe sperren die Projektzeile innerhalb einer PostgreSQL-Transaktion. Dadurch bleiben fortlaufende Ticketnummern, Hierarchieänderungen, Statusersetzungen und Mitgliedschaft konsistent. `expected_updated_at` schützt vollständige Ticketformulare optional vor dem Überschreiben neuerer Änderungen. Der Browser verwendet dieses Feld auch beim Verschieben.

Die vier festen Kategorien sind `open`, `in_progress`, `done` und `closed`. Jedes Projekt erhält einen nicht löschbaren Grundstatus pro Kategorie. Benutzerdefinierte Status werden innerhalb ihrer Kategorie über `position` geordnet. Die Registry verwendet für konkrete Status nur `status_id`, keine eingebauten Statusnamen oder veraltenden Enum-Listen. Status vor Entscheidungen über `list_statuses` oder `get_project` lesen.

Das Frontend unter `/dashboard` bietet Board und hierarchische Liste. Statusauswahlen werden aus den Projektdaten aufgebaut. Bei aktiver Seite werden Daten alle zehn Sekunden und bei Fensterfokus erneut gelesen. Es gibt keinen zusätzlichen Realtime-Dienst. Das Projekt-Snapshot lädt für diese Mini-Version alle Projekttickets; MCP-Suchen über `list_tickets` sind mit `offset` und `limit` paginiert. Für sehr große Projekte muss der Snapshot später paginiert werden.

## MCP lokal starten

Abhängigkeiten mit `make install` installieren und die Datenbank mit `make db` starten. Der Server verwendet das offizielle [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) und läuft über stdio:

```bash
.venv/bin/python backend/mcp_server.py --user deine-adresse@example.com
```

Der MCP-Client startet diesen Prozess selbst. Die Website und Django-HTTP-API müssen für MCP nicht laufen; PostgreSQL muss erreichbar sein. `--user` oder `TASKLANE_MCP_USER_EMAIL` ist erforderlich. Der Server prüft bei jedem Werkzeugaufruf das aktive Konto und dessen aktuelle Projektmitgliedschaft.

Beispiel für einen stdio-Client; absolute Pfade an den Checkout anpassen:

```json
{
  "mcpServers": {
    "tasklane": {
      "command": "/absoluter/pfad/tasklane/.venv/bin/python",
      "args": ["/absoluter/pfad/tasklane/backend/mcp_server.py"],
      "env": {"TASKLANE_MCP_USER_EMAIL": "deine-adresse@example.com"}
    }
  }
}
```

Die angemeldete Seite `/dashboard/mcp` erzeugt diese Konfiguration mit lokalen Pfaden und der eigenen E-Mail. Der Prozess ist eine lokale Verbindung für einen vertrauenswürdigen Host mit Dateisystem- und Datenbankzugriff. Es wird kein HTTP-MCP-Endpunkt und kein Fernzugriff veröffentlicht; dafür wäre ein separates Authentifizierungskonzept erforderlich. Anmeldedaten oder Sitzungstokens gehören nicht in MCP-Argumente.

Der Server bietet 24 Werkzeuge für Projekte, Mitgliedschaft, Status, Tags und Tickets. `list_projects` → `get_project` / `list_statuses` liefert den aktuellen Kontext. `create_ticket` mit `kind: "epic"` erstellt ein Epic; `parent_id` verknüpft Untertickets. `assignee_ids` und `tag_ids` sind ersetzende Listen. Bei `update_ticket` bleiben ausgelassene Felder unverändert; `null` löst Eltern-Ticket oder Datum. Domainfehler werden als MCP-Toolfehler zurückgegeben. Protokollausgaben laufen über stdout, Diagnose über stderr.

## Prüfen und Wiki

`make test` prüft die PostgreSQL-Modelle, Projektgrenzen, CSRF, Hierarchien, Statuswechsel, Eingabevalidierung, Konflikte sowie Discovery und Werkzeugaufrufe mit dem offiziellen MCP-Client. `make check` prüft Django, Migrationen und den Next.js-Produktionsbuild.

Migration `work.0002_wiki_guides` veröffentlicht eingefrorene Ausgangsfassungen der Benutzeranleitung (Sichtbarkeit `registered`) und dieser Entwickleranleitung (`internal`). Bestehende Wiki-Artikel werden nicht überschrieben. Die versionierten Quellen stehen unter `docs/tasklane-guide.md` und `docs/development/tasklane-mcp.md`; Änderungen an Dateien aktualisieren bestehende Datenbankartikel nicht automatisch.
