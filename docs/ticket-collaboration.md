# Gemeinsam an Tickets arbeiten

Öffne ein Ticket oder Epic im Dashboard. Die Reiter **Details**, **Checklisten**, **Kommentare**, **Anhänge**, **Verlauf** und **Zeiten** gehören zum selben Ticket. Änderungen anderer Clients erscheinen nach spätestens zehn Sekunden bei aktivem Fenster oder beim erneuten Fokussieren.

## Kommentare und Beschreibung

Beschreibungen und Kommentare unterstützen Markdown. Die Beschreibung lässt sich vor dem Speichern als Vorschau ansehen. Eingebettetes HTML und externe Bilder werden nicht ausgeführt bzw. nachgeladen. Kommentare haben eine Person und einen Zeitstempel. Nur die ursprüngliche Person darf ihren Kommentar bearbeiten oder entfernen. Bei einer zwischenzeitlichen Änderung neu laden, bevor du die Korrektur erneut eingibst.

**Datei anhängen** an einem Kommentar öffnet den Datei-Reiter mit dieser Zuordnung. Die Datei erscheint danach auch beim Kommentar. Das Entfernen eines Kommentars entfernt seinen Text; zugehörige Dateien bleiben am Ticket und können getrennt entfernt werden. Weitere Kommentare und Aktivitäten können seitenweise vollständig nachgeladen werden.

## Checklisten

Ein Ticket kann mehrere benannte Checklisten enthalten. Ergänze Punkte, hake sie ab, ändere ihre Texte, weise sie einem aktuellen Teammitglied zu und verschiebe sie mit den Pfeilen. Alle effektiven Projektmitglieder können Checklisten bearbeiten. Die Karte zeigt erledigte Punkte und Gesamtzahl. Die Checklistenverwaltung ist unabhängig vom Status des Tickets.

## Private Anhänge

Wähle eine oder mehrere Dateien oder ziehe sie in die Uploadfläche. Dateien werden nacheinander übertragen. Standardmäßig sind **50 MiB je Datei und 1 GiB je Ticket** erlaubt; die Installation kann andere Grenzen konfigurieren. Dateiname, Größe und SHA-256-Prüfsumme stehen am Anhang. Downloads erfordern bei jedem Abruf aktuellen Projektzugriff und werden als Datei ausgeliefert. Ein kopierter Downloadlink gewährt keine Berechtigung.

Die hochladende Person und die Projekt- bzw. Workspace-Leitung können eine Datei entfernen. Nach Entzug des Projektzugriffs sind auch zuvor bekannte Dateilinks nicht mehr nutzbar. Uploads haben eine Integritätsprüfung; nicht abgeschlossene Uploads laufen nach 24 Stunden ab. Die Administration kann diese später bereinigen.

## Eigene Felder

Unter **Workflow & Team → Eigene Felder** richtet die Projekt- oder Workspace-Leitung Felder ein. Es gibt Text, langen Text, Zahlen, Datum, Ja/Nein, Auswahl, Mehrfachauswahl und Links. Felder gelten entweder für jedes Ticket oder einmal für das Projekt, etwa eine Kundenreferenz am Ticket und ein Budget am Projekt.

Ticketfelder erscheinen im Reiter **Details**. Pflichtfelder müssen bei neuen Tickets ausgefüllt werden. Nachträglich angelegte Pflichtfelder blockieren das Lesen alter Tickets nicht. Schlüssel, Typ und Geltungsbereich bleiben stabil, damit API-Integrationen nicht durch Umbenennungen brechen. Verwendete Auswahlwerte können nicht einfach entfernt werden. Archivierte Felder und ihre gespeicherten Werte bleiben lesbar.

## Verlauf und Direktlinks

Der Verlauf zeigt die seit Einführung dieser Funktion aufgezeichneten Ticketänderungen, Kommentare, Checklisten, Felder, Anhänge und manuellen Zeitänderungen mit Person und Datum. Historische Ereignisse aus älteren Installationen werden nicht nachträglich erfunden. Ein Ticket-Direktlink enthält Workspace-, Projekt- und Ticket-ID und öffnet den Dialog für berechtigte Personen.

## Konto und Integration

Unter **Konto** änderst du Vor- und Nachnamen sowie dein Passwort mit dem bisherigen Passwort. Die eigene Sitzung bleibt beim Passwortwechsel angemeldet; andere Sitzungen müssen sich erneut anmelden. Google-Konten ohne bestehendes Passwort benötigen zur Passwortvergabe die Benutzerverwaltung.

Unter **API & MCP** legst du persönliche Schlüssel für andere Anwendungen an. Siehe die [API- und MCP-Anleitung](/wiki/tasklane-api-mcp). Projektzugriff folgt immer der aktuellen Mitgliedschaft; Staff-Rechte allein eröffnen keine fremden Projekte.
