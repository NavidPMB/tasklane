# Eigenständigen Tasklane-Dienst entwickeln und veröffentlichen

## Gemeinsame Fachlogik

`modules.work.services.OPERATIONS` enthält 63 JSON-Schema-validierte Aktionen. UI, stdio-MCP, Remote-MCP und API v1 führen dieselben Funktionen aus. Schreiboperationen sperren das Projekt in einer Datenbanktransaktion. Benutzeridentitäten kommen aus Sitzung, vertrauenswürdigem stdio-Prozess oder überprüftem API-Schlüssel, niemals aus frei übergebenen Argumenten.

`collaboration.py` implementiert Kommentare, Checklisten, typisierte Felder und Aktivitäten. Fremde Kommentare sind nicht bearbeitbar; Löschen entfernt den Text, behält die Zuordnung. Checklistenpunkte dürfen nur aktuellen effektiven Projektmitgliedern zugewiesen werden. Definitionen eigener Felder und Projektwerte verwaltet die Projekt-/Workspace-Leitung. Feldschlüssel, Typ und Scope bleiben stabil; verwendete Auswahloptionen sind geschützt. `expected_updated_at` liefert bei veralteten Änderungen einen Konflikt. Neue Aktivitäten werden mit Person und Zeitpunkt aufgezeichnet, vorhandene historische Änderungen nicht rekonstruiert.

Ticketlisten laden Kommentar-, Datei- und Checklistenanzahlen über separate Subqueries. Zeit-Summen dürfen durch zusätzliche Relation-Joins nicht multipliziert werden. Eigene Feldwerte werden vorab geladen. Das bestehende Projekt-Snapshot lädt weiterhin alle Tickets; der Suchendpunkt und neue Kommentare/Aktivitäten unterstützen Pagination.

## Private Dateien

`attachments.py` verwaltet UUID-Metadaten und Dateien ausschließlich unter `PRIVATE_FILE_ROOT`. Keine öffentliche MEDIA-Route hinzufügen. Dateinamen werden bereinigt; Speicherpfade stammen nur aus serverseitigen UUIDs. Neue Dateien sind `0600`, Verzeichnisse `0700`. Zustände: uploading, ready, deleted. Unvollständige Uploads verfallen nach 24 Stunden. Abschluss kontrolliert Größe und SHA-256; bekannte Quell-Prüfsummen werden ebenfalls geprüft. Chunks enthalten höchstens 64 KiB Rohdaten und müssen am gespeicherten Offset beginnen. Nach unvollständigem DB-Commit wird beim nächsten Schreibversuch auf den bestätigten Offset gekürzt.

Multipart-Uploads der Oberfläche verwenden dieselbe Chunk-Logik und CSRF. Downloads prüfen aktuelle Projektmitgliedschaft, setzen Attachment-Disposition, nosniff, CSP und no-store. Daten werden nicht als Browser-HTML ausgeführt. Nur Autor oder Projekt-/Workspace-Leitung können löschen; Dateilöschung erfolgt nach DB-Commit. Datenbank und privates Dateiverzeichnis gemeinsam sichern. `cleanup_uploads` zeigt standardmäßig nur abgelaufene Uploads/ClickUp-Pläne, `--apply` entfernt sie.

## Persönliche Integrationsschlüssel

`ApiToken` enthält den SHA-256-Digest zur Suche, Konto, Rechte, Ablauf, optionalen Workspace und PUBLIC_URL-Audience. Der Rohwert ist ausschließlich im zentral verschlüsselten `IntegrationCredential` gespeichert und wird nur beim Erstellen einmal zurückgegeben. Widerruf deaktiviert den Zugang und leert das verschlüsselte Secret. Aktives Konto, Ablauf, Audience und Projektzugriff werden erneut geprüft. `read`, `write` und `manage` begrenzen Funktionen zusätzlich zu den Benutzerrechten. Workspace-Schlüssel können nicht durch Projektlisten, Berichte, Dateien oder das Anlegen anderer Workspaces ausbrechen.

`/api/v1` akzeptiert ausschließlich Bearer-Authentifizierung und kein Sitzungscookie als Ersatz. Nur diese expliziten Integrationsendpunkte sind von Browser-CSRF ausgenommen. Schlüsselverwaltung bleibt unter `/api/work/access-tokens/` mit Sitzung und CSRF. OpenAPI und Capabilities entstehen aus derselben Registry. Neue Aktionen auf passende Stufenzuordnung und Workspace-Grenzen in `token_auth.py` prüfen.

## Remote-MCP und ASGI

`config.asgi` leitet `/mcp` an das offizielle SDK weiter, alle übrigen Routen an Django. Der Streamable-HTTP-Transport ist stateless und nutzt JSON-Antworten. Host, Origin und HTTPS werden kontrolliert; TLS-Weiterleitungsheader dürfen ausschließlich vom vertrauenswürdigen Proxy stammen. Ein `ContextVar` hält den Schlüssel je Anfrage getrennt. Aufruf und Discovery validieren ihn erneut; DB-Verbindungen werden an den Grenzen geschlossen. Es gibt keine OAuth-Ausstellung oder dynamische Clientregistrierung: Clients müssen Bearer-Header konfigurieren können.

Entwicklung über Uvicorn mit Reload und Djangos Staticfiles-ASGI-Handler bei `DEBUG`; `scripts/serve_backend.py` verwenden. Der alte WSGI-Server stellt Remote-MCP nicht bereit. Next.js wird mit `output: standalone` gebaut. `npm start` kopiert lokale statische Assets und startet den Standalone-Server. Build und laufender lokaler Next-Prozess dürfen nicht gleichzeitig dasselbe `.next` verändern. Docker verwendet den Standalone-Server direkt. Im Produktionsnetz leitet Caddy API/Auth/MCP direkt ans Backend, öffentliche UI ans Frontend. Beide Anwendungscontainer laufen ohne Root-Rechte.

## Prüfen

`make test` verwendet PostgreSQL und prüft Fachrechte, Verschlüsselung, Revocation, JSON-API, CSRF, Dateien, konkurrierende Änderungen sowie echte MCP-Aufrufe. `test_remote_mcp.py` startet einen lokalen ASGI-Server und verwendet den offiziellen SDK-Client für echte HTTP-Aufrufe und parallele Benutzer. Streaming-Dateitests verwenden `TransactionTestCase`, da Response-Abschluss DB-Verbindungen schließt.

`make check` prüft Django, fehlende Migrationen und den Next-Produktionsbuild. `make release-smoke` baut beide Docker-Images und startet einen isolierten HTTPS-Stack mit eigener Datenbank, Volumes und temporären Zugangsdaten. Es prüft tatsächliche Anmeldung, UI, Kommentare, Checklisten, Felder, privaten Upload/Download, API, Remote-MCP, sofortigen Widerruf und die Persistenz nach Containerneustart. Der Test entfernt anschließend ausschließlich seine eigenen Testcontainer und -volumes. Die Zertifikatsprüfung ist nur für dessen lokales selbstsigniertes Testzertifikat deaktiviert.

Oberfläche zusätzlich im Browser prüfen: Team-Workspace, eigene Felder, Ticket, Markdown, Checklistenreihenfolge/Zuweisung, Kommentar bearbeiten, Dateiupload/Download, Direktlink, Schlüssel erstellen/widerrufen, Profil/Passwort, eingeschränkte Teamrechte und schmale Bildschirmbreite. Keine echten Benutzerinhalte dafür löschen oder verändern.

## Veröffentlichung und Betrieb

`VERSION` und Frontend-Paketversion gemeinsam erhöhen, Release-Hinweise unter `docs/releases/<version>.md` ergänzen. CI führt PostgreSQL-Tests, Frontend-Build und den HTTPS-Container-Smoke-Test aus. Ein Tag `v<VERSION>` startet `.github/workflows/release.yml`; erst nach erfolgreicher CI werden amd64-/arm64-Images, Quellarchiv, SHA256SUMS und GitHub-Release veröffentlicht. Release-Tags nicht nachträglich überschreiben. Paket-Sichtbarkeit der GHCR-Images bei der ersten Veröffentlichung prüfen; der Quellbuild ist unabhängig davon verfügbar.

Die [Betriebsanleitung](../production.md) beschreibt DNS, HTTPS, eigene Benutzer, Backups, Wiederherstellung und Updates. Im Produktionsbetrieb nutzt Django einen PostgreSQL-Cache für gemeinsame Login-Limits; das Entrypoint legt die Cachetabelle idempotent an. Beim Betrieb außerhalb dieses Entrypoints nach den Migrationen `python manage.py createcachetable` ausführen. Entwicklungs-/Testsitzungen verwenden den lokalen Speichercache.

Die eigenständige Anwendung ist die Quelle ihrer eigenen Releases. LeonLab-SSO/Rechtezuordnung und die vollständige Legacy-Migration benötigen einen separaten Schnittstellenvertrag und einen vollständigen Export; sie sind kein Bestandteil dieses Releases. Jira-/ClickUp-Auswahlimporte behalten ihren beschriebenen Umfang, einschließlich des bewusst separat geprüften historischen ClickUp-Zeitimports.

## Wiki

`work.0012_standalone_guides` legt eingefrorene Ausgangsfassungen an: Zusammenarbeit und API (`registered`), Betrieb und Entwicklung (`internal`). Bestehende Artikel werden durch `get_or_create` erhalten. Interne Inhalte sind ausschließlich für aktive Superuser sichtbar, nicht für Staff allein. Änderungen an Dateien überschreiben keine redaktionell bearbeiteten Artikel. Bei Updates Dateifassung und Wiki-Inhalt gezielt gemeinsam pflegen; keine Secrets in Artikel oder Migrationen übernehmen.
