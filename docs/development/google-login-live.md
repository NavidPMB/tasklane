## Ziel

Google-Anmeldung für die eigene Live-Domain aktivieren. Diese Anleitung gehört zum internen Entwickler-Wiki und ist im Frontend ausschließlich für Superuser sichtbar. Sie enthält keine Zugangsdaten.

## 1. Live-Domain und Server konfigurieren

Die Website muss unter ihrer endgültigen HTTPS-Adresse erreichbar sein. Die folgenden Werte sind Beispiele; `app.example.com` durch die tatsächliche Domain ersetzen:

```dotenv
DJANGO_DEBUG=false
PUBLIC_URL=https://app.example.com
DJANGO_ALLOWED_HOSTS=app.example.com,127.0.0.1,backend
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com
BACKEND_URL=http://127.0.0.1:8002
```

`DJANGO_ALLOWED_HOSTS` muss auch den internen Host enthalten, den Next.js für Server-Anfragen verwendet, zum Beispiel `127.0.0.1` bei lokal laufendem Django. `BACKEND_URL` ist die interne Backend-Adresse; in einer Container-Umgebung kann sie anders lauten. Für mehrere öffentliche Domains die tatsächlich verwendeten Hosts und CSRF-Origins ergänzen.

Einen eigenen zufälligen `DJANGO_SECRET_KEY` und einen dauerhaften `CREDENTIAL_ENCRYPTION_KEY` auf dem Server konfigurieren. Den Verschlüsselungsschlüssel sicher getrennt von der Datenbank sichern und bei einem normalen Neustart oder Deployment beibehalten.

TLS am vertrauenswürdigen Reverse Proxy terminieren. Er muss eingehende Forwarded-Header überschreiben und Host sowie HTTPS-Protokoll korrekt an Next.js/Django weitergeben. Django mit einem geeigneten WSGI-/ASGI-Server betreiben. Die lokale Compose-Datei allein stellt noch kein Live-Deployment bereit. Nach Konfigurationsänderungen Backend und Frontend neu starten.

## 2. Eigenen Google-OAuth-Client anlegen

In der [Google Cloud Console](https://console.cloud.google.com/auth/overview) für den Live-Betrieb ein eigenes Google-Cloud-Projekt auswählen oder anlegen. Entwicklungs- und Live-Zugangsdaten getrennt halten.

Unter Google Auth Platform Branding, Support-Kontakt, Zielgruppe und Datenzugriff konfigurieren. Für die öffentliche Anmeldung die externe Zielgruppe wählen. Die Google-Einstellung „Internal“ beschränkt die App auf die zugehörige Google-Workspace-Organisation; sie hat nichts mit der Sichtbarkeit dieses Wikis zu tun.

Einen OAuth-Client vom Typ **Webanwendung** anlegen. Als autorisierte JavaScript-Quelle die öffentliche Origin ohne Pfad eintragen. Als autorisierte Weiterleitungs-URI dieselbe Origin mit `/accounts/google/login/callback/` eintragen. Für das Beispiel:

```text
JavaScript-Quelle: https://app.example.com
Weiterleitungs-URI: https://app.example.com/accounts/google/login/callback/
```

Schema, Host, Pfad und abschließender Schrägstrich müssen exakt stimmen. Nur die benötigten Profil- und E-Mail-Berechtigungen für den Login verwenden. Falls Google Nachweise, Domain-Verifizierung oder weitere Angaben zum Branding verlangt, diese im dortigen Prüfprozess ergänzen.

## 3. Client-ID und Secret im Django-Admin speichern

Mit einem Superuser unter `/django-admin/` anmelden. **Einstellungen → Integrationen & Zugangsdaten → Google Login** öffnen. Client-ID und Client-Secret des Live-Clients eintragen, **Aktiv** auswählen und speichern.

Die Zugangsdaten werden verschlüsselt gespeichert und ohne Neustart gelesen. Ein leer gelassenes Secret-Feld behält den vorhandenen Wert. Secrets niemals in Wiki-Artikel, Git, Browser-Konfiguration oder Screenshots kopieren.

Die aktuell aus `PUBLIC_URL` abgeleiteten Werte dieses Projekts sind:

```text
JavaScript-Quelle: {{PUBLIC_URL}}
Weiterleitungs-URI: {{GOOGLE_CALLBACK_URL}}
```

Solange hier noch `localhost` oder `127.0.0.1` steht, ist `PUBLIC_URL` noch auf lokale Entwicklung eingestellt. Im Django-Admin werden dieselben Projekt-URLs angezeigt.

## 4. Zielgruppe und Veröffentlichungsstatus prüfen

Bei einer externen App den Veröffentlichungsstatus in Google Auth Platform prüfen. Für eine allgemein verfügbare Anmeldung **In production** verwenden. Während gezielter Tests gegebenenfalls die erlaubten Testnutzer eintragen. Welche Test- und Prüfregeln gelten, hängt von Zielgruppe und angefragten Berechtigungen ab; die Hinweise der Google Console beachten.

Eine Freigabe durch Google macht niemanden zum Administrator dieser Website. Neue Google-Konten erhalten zunächst normale Benutzerrechte. Staff- und Superuser-Rechte werden separat durch die eigene Administration vergeben.

## 5. Anmeldung im Live-Betrieb testen

1. Die HTTPS-Website in einem privaten Browserfenster öffnen und `/login` aufrufen.
2. Mit Google anmelden. Nach erfolgreicher Rückleitung muss `/dashboard` erscheinen.
3. Mit einem normalen Benutzer prüfen, dass `/admin` und interne Wiki-Artikel nicht zugänglich sind.
4. Abmelden und prüfen, dass das Dashboard anschließend wieder eine Anmeldung verlangt.
5. Die öffentliche Wiki-Ansicht ohne Sitzung prüfen; dort dürfen keine internen Titel oder Inhalte erscheinen.

Die erstmalige Einrichtung erfolgt über einen separaten administrativen Zugang. Ein bereits bestehendes lokales Konto wird nicht allein aufgrund derselben E-Mail-Adresse mit Google verknüpft.

## Häufige Fehler

- **redirect_uri_mismatch:** Die im Admin angezeigte Callback-URL mit dem Google-Client vergleichen; auch HTTPS, Subdomain und abschließenden Slash prüfen.
- **Zugriff durch Google abgelehnt:** Zielgruppe, Veröffentlichungsstatus und gegebenenfalls Testnutzer prüfen.
- **CSRF-Fehler oder verlorene Sitzung:** Öffentliche Origin, vertrauenswürdige CSRF-Origins, HTTPS und Forwarded-Header des Proxys prüfen. Cookies müssen für dieselbe öffentliche Domain gesetzt werden.
- **Google-Button deaktiviert:** Client-ID, gespeichertes Secret und den Aktiv-Schalter unter Integrationen prüfen.
- **Zugangsdaten nicht entschlüsselbar:** Prüfen, ob der Server den ursprünglichen `CREDENTIAL_ENCRYPTION_KEY` verwendet. Den bestehenden Schlüssel nicht durch einen neuen zufälligen Wert ersetzen.

## Offizielle Dokumentation

- [Google OAuth für Webserver und exakte Weiterleitungs-URIs](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google-Zielgruppe und Veröffentlichungsstatus](https://support.google.com/cloud/answer/15549945)
- [Google-Verifizierung und getrennte Entwicklungs-/Produktionsprojekte](https://support.google.com/cloud/answer/13461325)
- [Google-Provider in django-allauth](https://docs.allauth.org/en/latest/socialaccount/providers/google.html)
