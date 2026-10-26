# Tasklane auf einer eigenen Domain betreiben

Tasklane läuft unabhängig von LeonLab oder anderen Anwendungen. Oberfläche, Anmeldung, PostgreSQL, private Dateien, API und Remote-MCP werden zusammen veröffentlicht. Ein Linux-Server mit Docker Compose und Git genügt; Python 3 wird nur zum Erzeugen der Konfiguration gebraucht. Caddy übernimmt HTTPS, Django läuft unter Uvicorn/ASGI, Next.js als Standalone-Server. PostgreSQL ist auch der gemeinsame Login-Limit-Cache; ein zusätzlicher Cache-Dienst ist nicht erforderlich.

## Erstinstallation

Die Domain, beispielsweise `tasks.example.com`, muss per DNS auf den Server zeigen. Eingehende Ports 80 und 443 freigeben. Backend und Datenbank werden nicht öffentlich veröffentlicht.

```bash
git clone --branch v0.2.1 https://github.com/NavidPMB/tasklane.git
cd tasklane
python3 scripts/init_production.py --domain tasks.example.com
make production-build
make production-up
make production-user
```

Der Generator erstellt `.env.production` mit zufälligen, unabhängigen Secrets und Dateirechten `0600`; bestehende Dateien werden nicht überschrieben. `make production-user` fragt interaktiv nach deiner eigenen E-Mail und deinem Passwort. Es gibt kein Standardkonto. Öffne danach `https://tasks.example.com/login`. Weitere Benutzer können über `/django-admin/` angelegt werden; Workspace-Mitgliedschaften werden in Tasklane verwaltet.

`make production-up` wartet auf die Dienstprüfungen. Mit `make production-logs` die letzten Meldungen ansehen. `make production-stop` entfernt die Container und das Netz, erhält aber die Datenvolumes. Die Produktionsinstallation verwendet andere Volumes als die lokale Entwicklung. Sie übernimmt bestehende lokale Daten nicht automatisch.

Die Release-Automation veröffentlicht Backend- und Frontend-Images für amd64/arm64 in GHCR. Alternativ zum Quellbuild können verfügbare Images geladen werden:

```bash
docker compose --env-file .env.production -f compose.production.yaml pull
docker compose --env-file .env.production -f compose.production.yaml up -d --wait
```

Das Deployment verwendet die in `.env.production` festgelegte numerische `TASKLANE_VERSION`, nicht automatisch `latest`. Prüfe die tatsächliche Verfügbarkeit der gewünschten Images oder nutze `make production-build` aus dem passenden Release-Checkout.

## Einstellungen und Anmeldung

`.env.production` bleibt ausschließlich auf dem Server bzw. im privaten Backup. `PUBLIC_URL`, `TASKLANE_DOMAIN`, `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS` müssen dieselbe öffentliche Domain beschreiben. Einen eigenen Reverse Proxy nur mit vertrauenswürdig gesetzten Host-/Proto-Headern einsetzen und den Backend-Port weiterhin intern halten. Der mitgelieferte Caddy übernimmt dies bereits.

Google ist optional: Im Django-Admin unter **Integrationen & Zugangsdaten → Google Login** eigene OAuth-Daten verschlüsselt speichern. Callback: `https://tasks.example.com/accounts/google/login/callback/`. Nur Superuser können Zugangsdaten verwalten. Die E-Mail-/Passwortanmeldung benötigt Google nicht. Profil und bestehendes Passwort ändern Benutzer unter **Konto**; ein vergessenes Passwort kann die Benutzerverwaltung zurücksetzen oder interaktiv:

```bash
docker compose --env-file .env.production -f compose.production.yaml exec backend \
  python manage.py changepassword you@example.com
```

Die Installation versendet standardmäßig keine Passwort-Reset-E-Mails und keine Einladungen. Automatische öffentliche Registrierung ist nicht aktiv.

Private Dateien liegen ausschließlich im Volume `production_files`. Standardgrenzen: `ATTACHMENT_MAX_BYTES=52428800` und `ATTACHMENT_TICKET_MAX_BYTES=1073741824`. Bei höheren Datei-Limits auch Caddys `max_size` in `deploy/Caddyfile` anpassen. Festplattenkapazität und Backupgröße entsprechend einplanen.

## Backups und Wiederherstellung

Ein vollständiges Backup enthält **PostgreSQL, private Dateien und `.env.production` samt `CREDENTIAL_ENCRYPTION_KEY`**. Ohne den ursprünglichen Verschlüsselungsschlüssel können gespeicherte Integrationszugänge nicht wieder entschlüsselt werden. Die TLS-Volumes können ebenfalls gesichert werden; statische Dateien sind aus dem Build rekonstruierbar.

Für einen konsistenten Stand während des Backups Schreibzugriffe stoppen:

```bash
umask 077
mkdir -p backups
docker compose --env-file .env.production -f compose.production.yaml stop proxy frontend backend
docker compose --env-file .env.production -f compose.production.yaml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/database.dump
docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps -T \
  --entrypoint tar backend -C /data/private -cf - . > backups/private-files.tar
cp .env.production backups/environment.private
docker compose --env-file .env.production -f compose.production.yaml up -d --wait
```

Backups geschützt auf einem getrennten Datenträger aufbewahren und Wiederherstellung regelmäßig in einer isolierten Umgebung erproben. Für eine Wiederherstellung auf **frisch angelegten Volumes** dieselbe Release-Version und die gesicherte `.env.production` verwenden, zunächst nur `db` starten, dann:

```bash
docker compose --env-file .env.production -f compose.production.yaml exec -T db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < backups/database.dump
docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps -T \
  --entrypoint tar backend -C /data/private -xf - < backups/private-files.tar
docker compose --env-file .env.production -f compose.production.yaml up -d --wait
```

Die entpackten Dateien müssen für UID 10001 des Backend-Containers lesbar sein. Die Beispiele verwenden dessen Benutzer. Beim Wiederherstellen in bereits gefüllte Datenbanken muss ein eigener, vorher geprüfter Wiederherstellungsplan verwendet werden.

## Updates und Betrieb

Vor einem Update Backup erstellen, Release-Hinweise lesen und den passenden Git-Tag auschecken. `TASKLANE_VERSION` in `.env.production` anpassen; weitere Secrets erhalten. Mit `make production-build` aus dem Release-Checkout bauen oder die entsprechenden veröffentlichten Images laden. Danach `make production-up`: Das Backend führt Migrationen und `collectstatic` aus, bevor Uvicorn startet. Nicht rückwärts auf eine ältere Datenbankstruktur wechseln; bei inkompatiblen Migrationen das passende Backup wiederherstellen.

`GET /api/health/` meldet Version und API-Version. Überwache Erreichbarkeit, Speicherplatz, Backups und Containerzustand. Abgebrochene Uploads und abgelaufene ClickUp-Prüfpläne zunächst prüfen und anschließend bereinigen:

```bash
docker compose --env-file .env.production -f compose.production.yaml exec backend python manage.py cleanup_uploads
docker compose --env-file .env.production -f compose.production.yaml exec backend python manage.py cleanup_uploads --apply
```

Der erste Aufruf ist eine Vorschau. Ein täglicher Aufruf mit `--apply` ist möglich. Fertige Anhänge werden dadurch nicht gelöscht.

## Andere Anwendungen verbinden

Persönliche Schlüssel werden im Dashboard erstellt. API: `https://tasks.example.com/api/v1`, OpenAPI: `/api/v1/openapi.json`, Remote-MCP: `/mcp` mit Streamable HTTP und Bearer-Header. Die [Integrationsanleitung](api.md) erklärt Rechte und Dateiübertragung. Tasklane kann so von anderen Projekten verwendet werden, ohne deren Build oder Release abzuwarten. Eine LeonLab-SSO-Anbindung und der separate vollständige Legacy-Import sind zukünftige Integrationsarbeiten.
