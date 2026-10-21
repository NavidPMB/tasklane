# Entwicklerdokumentation

## Tasklane lokal einrichten

Tasklane nutzt einen eigenen Compose-Projektnamen und eine eigene PostgreSQL-Datenbank (`tasklane`). `make setup` erzeugt eine lokale `.env` mit unabhängigen Secrets, installiert die Abhängigkeiten und führt die Migrationen aus. `frontend/package-lock.json` fixiert die Frontend-Abhängigkeiten für `npm ci`.

Die Standardports für dieses Projekt sind Frontend `3010`, Backend `8010` und PostgreSQL `5440`, damit andere lokale Projekte auf den Core-Standardports weiterlaufen können. Anschließend `make dev` für beide Dienste in einem Terminal starten; alternativ `make backend` und `make frontend` in getrennten Terminals. `make user` legt im interaktiven Terminal den ersten Administrator an. Vor der ersten Anmeldung einen eigenen Superuser gemäß README anlegen oder eigene Google-OAuth-Zugangsdaten konfigurieren.

Ticket- und Projektfunktionen liegen in `backend/modules/work/`. HTTP und MCP teilen dieselbe Registry und Fachlogik. Die [Tasklane- und MCP-Entwickleranleitung](development/tasklane-mcp.md) beschreibt Berechtigungen, Statusmodell, lokale Verbindung und Prüfungen. Die [Benutzeranleitung](tasklane-guide.md) erklärt die Oberfläche. Neue Fachmodule gehören unter `backend/modules/`; Anmeldung, Berechtigungsprüfung und gemeinsame Shell werden weiterverwendet.

## Lokaler Schnellstart und MCP-Hilfen

`make dev` startet PostgreSQL und anschließend Backend und Frontend über `scripts/run_dev.py`. Der Supervisor beendet bei Ctrl+C, SIGTERM oder dem Ausfall eines Dienstes beide Prozessgruppen einschließlich Reload-Prozessen. Die Datenbank bleibt unabhängig davon verfügbar und kann mit `make stop` beendet werden.

`make mcp-config MCP_EMAIL=you@example.com` gibt eine JSON-Konfiguration mit absoluten Pfaden des aktuellen Checkouts aus. `make mcp-check MCP_EMAIL=you@example.com` prüft die echte stdio-Verbindung anhand von Tool-Discovery und `list_projects`, ohne Daten zu ändern. Die E-Mail muss zu einem bestehenden aktiven lokalen Konto gehören. Beide Hilfen setzen die virtuelle Python-Umgebung voraus.

## Zeitbuchungen und Berichte

`modules.work.TimeEntry` speichert Datum, ganze Minuten (1–1440), Notiz, Ticket und die buchende Person. Die Autorenschaft kommt ausschließlich aus der Sitzung bzw. der MCP-Identität. Fremde Buchungen dürfen auch von der Projektleitung nicht verändert werden; lesender Zugriff folgt der aktuellen Projektmitgliedschaft. Buchungen bleiben bei Mitgliedschaftsentzug erhalten, Tickets mit Buchungen sind vor dem Löschen geschützt. Es gibt keinen laufenden Timer und keine automatische Verrechnung von Untertickets auf Epics.

Die sechs Zeit-Werkzeuge sind in derselben `OPERATIONS`-Registry wie die Ticketaktionen registriert. Schreibaktionen bleiben CSRF-geschützte `POST /api/work/actions/`. Lesende Browserrouten sind `/api/work/time/entries/`, `/api/work/time/report/` und `/api/work/time/export/`. Optionale Filter: `workspace_id`, `project_id`, `user_id`, `date_from`, `date_to`; Buchungslisten zusätzlich `ticket_id`, `offset`, `limit`. Zeiträume sind inklusive, Berichte standardmäßig vom Monatsanfang bis heute. Ohne Projektfilter werden nur aktuell zugängliche Projekte summiert. Buchungslisten ohne Datumsfilter zeigen die gesamte Historie.

Summen werden in PostgreSQL als ganze Minuten berechnet. Ticketantworten enthalten `logged_minutes`; Listen laden diese Summe über eine Annotation, ohne M2M-Zuweisungen mitzusummieren. Ein Buchungstag ist ein Kalendertag mit einer Buchung. CSV verwendet Semikolon und UTF-8-BOM; Textfelder mit Formelpräfixen werden geschützt. Exporte verwenden dieselben Zugriffs- und Filterregeln wie Berichte. `expected_updated_at` schützt optional vor konkurrierenden Korrekturen.

[Benutzeranleitung](time-tracking.md), auch unter `/wiki/tasklane-arbeitszeit` mit Sichtbarkeit `registered`. Migration `work.0004_time_guide` legt den eingefrorenen Ausgangsstand an, ohne bestehende Wiki-Artikel zu überschreiben. Die Tests in `modules.work.test_time` prüfen Summen, Filter, Datum und Dauer, Autorenschaft, Mitgliedschaftsentzug, CSV und echte MCP-Aufrufe.

## Workspaces und Jira Cloud

Die [Benutzeranleitung für Workspaces und Jira](workspaces-jira.md) beschreibt Teamfreigaben und den Auswahlimport. Die [technische Anleitung](development/workspaces-jira.md) dokumentiert Berechtigungsvererbung, verschlüsselte Zugangsdaten, Cloud- und Gateway-Zugriffe, Transaktionsgrenzen und Quellzuordnungen. Neue Konten werden nicht aus Jira übernommen; eine Zuweisung setzt eine passende E-Mail eines aktiven effektiven Projektmitglieds voraus.

Workspace-Mitglieder erhalten Zugriff auf bestehende und zukünftige Projekte. Alte direkte Projektfreigaben bleiben beim Upgrade erhalten, ohne bisher private Projekte zu öffnen. `workspace_id` grenzt Projektlisten und Zeitberichte ein. Der Jira-Import liest vor dem Schreiben erneut aus Jira und speichert bis zu 50 gewählte Tickets atomar; existierende Quell-Tickets werden übersprungen. Jira-HTTP-Anfragen laufen außerhalb der DB-Transaktion. API-Tokens werden ausschließlich im zentralen verschlüsselten Integrationsmodell gespeichert.

Die Wiki-Ausgangsfassungen unter `/wiki/tasklane-workspaces-jira` (`registered`) und `/wiki/tasklane-workspaces-jira-entwicklung` (`internal`) werden durch `work.0007` eingefroren angelegt, ohne bestehende Inhalte zu überschreiben. Automatisierte Jira-Tests verwenden simulierte Netzwerkantworten; ein echter Import benötigt eigene Jira-Cloud-Zugangsdaten.

## ClickUp und historische Arbeitszeit

[Benutzeranleitung](clickup-import.md) und [technische Anleitung](development/clickup-import.md) dokumentieren den Import abgeschlossener Aufgaben samt Zeitbuchungen aus allen Jahren. Sechs zusätzliche API-/MCP-Aktionen prüfen und übernehmen maximal 20 Aufgaben je Durchlauf. Netzwerkabruf und Vollständigkeitsprüfung laufen vor der atomaren Übernahme eines 30 Minuten gültigen Importplans. Zugangsdaten bleiben ausschließlich im zentralen verschlüsselten Integrationsmodell.

Ursprüngliche Personen ohne passendes aktives Projektkonto bleiben historische Mitwirkende ohne Login oder Projektfreigabe. Zeitberichte unterstützen deren negative Personen-IDs; normale Konto-IDs bleiben positiv. Importierte Arbeitszeit ist schreibgeschützte Quellhistorie und verwendet exakte Millisekunden statt gerundeter Kompatibilitätsminuten. Alle Summen verwenden `time_values.minute_sum`; die bisherigen manuellen Buchungen und ihre Rechte bleiben erhalten. CSV ergänzt Originalperson, Quelle und Dauer in Millisekunden. Der Ergebnislink übergibt den historischen Zeitraum an den Bericht.

Die Migrationen `work.0008` und `0009` ergänzen Quellmodelle und Zeit-Constraints. `work.0010` erstellt eingefrorene Wiki-Anleitungen mit Sichtbarkeit `registered` bzw. `internal`, ohne bestehende Artikel zu überschreiben. Die Tests verwenden simulierte ClickUp-Antworten; Live-Übernahmen benötigen eigene Zugangsdaten mit den nötigen ClickUp-Teamzeitrechten. Nach Änderungen `make test` und `make check` ausführen.

## Passwortanmeldung

`POST /api/auth/login/` in `accounts.views.password_login` nimmt ausschließlich ein JSON-Objekt mit `email` und `password` an. Die Anfrage benötigt den CSRF-Token aus `GET /api/auth/session/` sowie das zugehörige Cookie. Erfolgreiche Anmeldung nutzt Django-Sitzungen mit HttpOnly-Cookies und rotiert Sitzungsschlüssel und CSRF-Token. Der Client wechselt anschließend auf `/dashboard`; Passwörter und Tokens werden nicht im Browser-Speicher abgelegt.

Die Authentifizierung verwendet den bestehenden allauth-Adapter mit den konfigurierten Django-Backends. E-Mail-Adressen werden normalisiert. Unbekannte Konten, falsche Passwörter, deaktivierte Konten und Konten ohne Passwort liefern dieselbe Fehlermeldung (`401`). allauth begrenzt fehlgeschlagene Versuche je E-Mail und IP und liefert bei Überschreitung `429`. Die vorhandene Google-Anmeldung bleibt erhalten; allauth-eigene Passwort-/Registrierungsseiten bleiben durch `SOCIALACCOUNT_ONLY` deaktiviert. Die Tasklane-Passwortanmeldung ist der explizite API-Einstieg für bestehende Konten.

Neue Konten über `createsuperuser` oder die vorhandene Benutzerverwaltung anlegen und Passwörter mit Djangos `changepassword` setzen. Keine Zugangsdaten in Quellcode, Dokumentation, Migrationen oder Beispieldateien hinterlegen. Der lokale Einprozessbetrieb verwendet Djangos Standardcache für Rate-Limits; bei mehreren Backend-Prozessen einen gemeinsamen Django-Cache konfigurieren, damit die Limits über alle Prozesse gelten.

`accounts.tests.PasswordLoginTests` prüft Anmeldung, Normalisierung, CSRF, Fremd-Origins, Rollen, Sitzungsrotation, Abmeldung, Eingabevalidierung und Rate-Limits. Danach `make test` und `make check` ausführen.

## Gemeinsames Wiki

Das Frontend stellt unter `/wiki` eine gemeinsame Wissensbasis bereit. Öffentliche Hilfe, Dokumentation für angemeldete Benutzer und interne Entwickleranleitungen werden im selben Modell `modules.wiki.Article` verwaltet. Es gibt keine getrennten Wiki-Anwendungen pro Zielgruppe.

- `public`: für alle Leser sichtbar.
- `registered`: zusätzlich für aktive, angemeldete Benutzer sichtbar.
- `internal`: zusätzlich ausschließlich für aktive Superuser sichtbar. Staff-Rechte allein reichen nicht.

Alle Frontend-Artikel müssen veröffentlicht sein. Entwürfe bleiben selbst für Superuser im Frontend verborgen; ihre Bearbeitung erfolgt im Django-Admin. Neue Artikel sind standardmäßig intern und unveröffentlicht. Nur Superuser dürfen Artikel anlegen, bearbeiten oder ihre Sichtbarkeit ändern.

Die APIs `/api/wiki/` und `/api/wiki/<slug>/` wenden die Zugriffsregeln vor Suche, Filterung und Serialisierung an. Direkte Links auf fehlende oder nicht zugängliche Artikel liefern dieselbe 404-Antwort. API-Antworten werden nicht geteilt gecacht. Keine vollständigen Artikelsammlungen an den Browser senden und dort ausblenden.

Artikel werden unter **Django-Admin → Wiki → Wiki-Artikel** als Markdown gepflegt. Das Frontend rendert Markdown ohne eingebettetes HTML oder externe Bilder. Die beiden erlaubten Platzhalter `{{PUBLIC_URL}}` und `{{GOOGLE_CALLBACK_URL}}` werden bei der Auslieferung aus der aktuellen Serverkonfiguration ersetzt. Eine allgemeine Template-Ausführung ist nicht vorgesehen. Secrets gehören ausschließlich in die verschlüsselte Integrationsverwaltung.

## Dokumentation bei Änderungen

Bei neuen Funktionen und Betriebsabläufen die Entwicklerdokumentation mitpflegen. Wiederkehrende Einrichtungsschritte und technische Anleitungen als interne Wiki-Artikel dokumentieren. Benutzer- oder Serviceanleitungen im selben Wiki ergänzen, sobald es dafür einen konkreten Bedarf gibt; ihre Zielgruppe bewusst auf `registered` oder `public` setzen. Entwicklerdetails werden durch neue öffentliche Hilfetexte nicht automatisch öffentlich.

Änderungen an Wiki-Berechtigungen mit Tests für anonyme Leser, Mitglieder, Staff und Superuser prüfen. Mindestens direkte Detailaufrufe, Suche, Entwürfe und den Entzug zuvor erlaubter Sichtbarkeit abdecken. Danach `make test` und `make check` ausführen.

## Google Login live schalten

Die erste Anleitung steht im Frontend unter **`/wiki/google-login-live`**, ausschließlich für Superuser. Die versionierte Ausgangsfassung liegt in [google-login-live.md](development/google-login-live.md).

Migration `wiki.0002_google_live_guide` enthält einen eingefrorenen Snapshot dieses Dokuments und erstellt den anfänglichen internen Artikel bei neuen Installationen. Danach ist die Datenbank die Quelle für das laufende Wiki; Änderungen über den Admin werden durch spätere Migrationen nicht ungefragt überschrieben. Eine Änderung an der Markdown-Datei allein aktualisiert bestehende Datenbankeinträge nicht. Bei einer fachlichen Aktualisierung den Wiki-Artikel und die versionierte Entwickleranleitung gemeinsam pflegen und gegebenenfalls eine gezielte Datenmigration ergänzen.

## Frontend-Konfiguration beim Build

Dev-Server, Build und Produktionsstart verwenden denselben Environment-Loader in `frontend/scripts/serve.mjs`. Er lädt die `.env` im Projektstamm vor dem Next.js-Prozess. `BACKEND_URL` wird für Proxy-Rewrites beim Build ausgewertet; nach einer Änderung neu bauen. Bei Änderungen am Startskript einen Produktionsbuild und den API-Proxy mit einem abweichenden Backend-Port prüfen.
