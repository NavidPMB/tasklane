# Projektregeln

- Mit dem Benutzer auf Deutsch kommunizieren.
- `README.md` beschreibt Einrichtung, Architektur und Google-Konfiguration.
- `docs/DEVELOPMENT.md` beschreibt Entwicklerabläufe und die Wiki-Regeln. Neue Funktionen und Einrichtungsschritte dort sowie bei Bedarf als interne Wiki-Anleitung dokumentieren; öffentliche Service- und Benutzerhilfe liegt im selben Wiki.
- Das Wiki unter `/wiki` verwendet ein gemeinsames Artikelmodell mit `public`, `registered` und `internal`. Interne Artikel sind ausschließlich für aktive Superuser sichtbar, niemals für Staff allein. Berechtigungen vor Suche, Listenbildung und Detailausgabe im Backend anwenden; Entwürfe nicht ausliefern.
- Fachliche Funktionen unter `backend/modules/` und passenden Frontend-Routen ergänzen. Wiederverwendbare Infrastruktur in `core`, `accounts`, `integrations` und `components/shell` halten.
- Namen und Farben zentral in `frontend/src/config/project.ts`, Navigation in `frontend/src/config/navigation.ts` ändern. Komponenten verwenden CSS-Variablen statt eigener Markenfarben.
- CMS ist die öffentliche Landingpage. Dashboard erfordert eine Sitzung; Admin zusätzlich Staff-Rechte. Zugriff auf Zugangsdaten im Django-Admin ist Superusern vorbehalten.
- Backend-Berechtigungen und CSRF-Prüfung erhalten. Keine Tokens im Browser-Speicher und keine Zugangsdaten im Frontend.
- `.env`, entschlüsselte Secrets und Datenbankinhalte niemals committen. Integrations-Secrets ausschließlich über das zentrale Modell verschlüsselt speichern.
- PostgreSQL auch für Tests verwenden. Nach relevanten Änderungen `make test` und `make check` ausführen.
- Kein neues Authentifizierungssystem, UI-Framework oder zusätzlicher Dienst ohne fachlichen Bedarf. Die Grundlage soll klein und klonbar bleiben.
