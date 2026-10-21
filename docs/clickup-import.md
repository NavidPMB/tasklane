# ClickUp-Aufgaben mit historischer Arbeitszeit übernehmen

## Vorbereiten

Öffne **Dashboard → ClickUp-Import** und wähle den Tasklane-Ziel-Workspace. Nur dessen Leitung kann ClickUp verbinden und Importe ausführen. Alle Mitglieder dieses Workspaces erhalten anschließend Zugriff auf seine Projekte und Zeitberichte.

Erzeuge für deine eigene ClickUp-Migration einen persönlichen API-Token unter **ClickUp → Einstellungen → Apps** und speichere ihn über **Verbindung prüfen & speichern**. Der Token wird nach erfolgreicher Profilprüfung im zentralen Integrationsmodell verschlüsselt gespeichert. Er wird nicht zurückgegeben oder im Browser-Speicher abgelegt. Ein neuer Token kann über dasselbe Formular hinterlegt werden.

Für die Zeitbuchungen anderer Personen benötigt das verwendete ClickUp-Konto Workspace-Owner- oder Admin-Rechte. Der Import fordert Teamzeiten ausdrücklich an, statt nur die standardmäßig sichtbaren eigenen Buchungen der letzten 30 Tage zu laden. Siehe [ClickUp-Anmeldung und persönliche Tokens](https://developer.clickup.com/docs/authentication) und [Berechtigungen der Zeit-API](https://developer.clickup.com/reference/gettimeentrieswithinadaterange).

## Auch abgeschlossene Aufgaben auswählen

Wähle nacheinander den **ClickUp-Workspace**, **Space**, optional einen **Ordner** und eine **Liste**. Mit den Archiv-Optionen erreichst du archivierte Bereiche oder Aufgaben. **Nur erledigte / geschlossene Aufgaben** ist anfangs eingeschaltet, damit du abgeschlossene Arbeit gezielt übernehmen kannst. Du kannst den Filter ausschalten, um auch offene Aufgaben zu sehen.

**Aufgaben laden** enthält Unteraufgaben und berücksichtigt auch abgeschlossene Tickets. Weitere Ergebnisse lassen sich seitenweise nachladen. Wenn eine gefilterte Seite leer ist und weitere Seiten existieren, verwende **Weitere Aufgaben laden**.

Wähle bis zu **20 Aufgaben pro Durchlauf**, auch aus mehreren Listen desselben ClickUp-Workspaces. Die Auswahl bleibt beim Wechsel zwischen dessen Listen erhalten. Eltern-Aufgaben ebenfalls auswählen, wenn ihre Hierarchie übernommen werden soll. Ein Wechsel des ClickUp-Workspaces setzt die Auswahl zurück. Vorhandene lokale Tickets bleiben auswählbar, um später fehlende Zeitbuchungen zu ergänzen.

## Gesamte Zeithistorie prüfen

**Tickets & gesamte Zeithistorie prüfen** liest die gewählten Aufgaben und die zugehörigen Einzelbuchungen aus **allen Jahren** erneut aus ClickUp. Es gibt keine automatische Beschränkung auf den aktuellen Monat oder die letzten 30 Tage.

Die Prüfung vergleicht die Summe der Einzelbuchungen mit der von ClickUp gemeldeten Ticket-Zeitsumme. Wenn nötig, werden frühere Mitwirkende über den bisherigen Task-Zeitendpunkt ermittelt und ihre Buchungen anschließend über die aktuelle Zeit-API geladen. Fehlen Berechtigungen, stimmen die Summen nicht überein oder läuft noch ein Timer, wird der Durchlauf abgebrochen. Es entstehen dabei keine lokalen Projekte, Tickets oder Zeitbuchungen. Stoppe einen laufenden Timer in ClickUp und starte die Prüfung erneut. Bei API-Drosselung kurz warten und den Durchlauf erneut prüfen.

Die Vorschau zeigt Aufgabenanzahl, Anzahl der Zeitbuchungen, Gesamtzeit, ursprüngliche Personen und Zeitraum. Dieser geprüfte Stand bleibt **30 Minuten** für den anschließenden Import gültig. Danach oder nach einer Tokenänderung erneut prüfen. Die Übernahme verwendet genau diesen geprüften Stand; es handelt sich um eine Momentaufnahme, nicht um eine laufende Synchronisierung.

## Personen, Dauer und Datum bleiben nachvollziehbar

Die ursprüngliche ClickUp-Person bleibt in der Quellhistorie jeder Buchung erhalten. Passt ihre E-Mail zu einem aktiven Mitglied des Zielprojekts, wird die Buchung diesem Tasklane-Konto zugeordnet. Andere Personen erscheinen als **ClickUp-Historie** in den Berichten, einschließlich ihres ursprünglichen Namens und der verfügbaren E-Mail. Dafür werden weder Konten angelegt noch Zugriffsrechte vergeben. Frühere Mitarbeitende können so weiterhin in historischen Auswertungen erscheinen.

Dauern werden in **Millisekunden** gespeichert, ohne sie auf ganze Minuten aufzurunden. Die Anzeige unterstützt Sekunden und Sekundenbruchteile. Das Buchungsdatum folgt dem ursprünglichen Startzeitpunkt in der bei der Prüfung verwendeten Tasklane-Zeitzone, derzeit **Europe/Berlin**. Eine Buchung über Mitternacht bleibt ihrem Startdatum zugeordnet. Buchungen über 24 Stunden werden intern in mehrere Teile mit derselben Quelle und demselben Startdatum aufgeteilt; die Gesamtdauer bleibt exakt. Buchungen mit Dauer null erzeugen keine Arbeitszeit und werden in den Hinweisen genannt.

Importierte Buchungen sind als Quellhistorie **nur lesbar**, auch für die zugeordnete Person. Neue eigene Buchungen können wie bisher ergänzt und bearbeitet werden. Die ursprüngliche Notiz, Quell-ID und Originalperson bleiben nachvollziehbar. Eine in ClickUp nachträglich geänderte, bereits importierte Buchung wird nicht überschrieben: Der erneute Import meldet den Konflikt und rollt den Durchlauf zurück.

## Importieren und Berichte öffnen

**Tickets und Zeiten importieren** legt pro ClickUp-Liste ein Projekt im gewählten Tasklane-Workspace an. Namensgleiche oder schon belegte Projektkürzel erhalten einen freien Suffix. Titel, Beschreibung, Status, Tags, Priorität, Fälligkeitsdatum und auflösbare Elternbeziehungen werden übernommen. ClickUp-Aufgaben werden als Tickets mit ihrer Unterticket-Hierarchie abgebildet. Status erscheinen wie gewohnt im Board, in Auswahlfeldern und über MCP. Die Ticketdetails enthalten einen Link zum ursprünglichen ClickUp-Ticket.

Das Ergebnis nennt neue Projekte und Tickets, übernommene Zeitbuchungen und deren Dauer sowie bereits vorhandene Quellen und Zuordnungshinweise. **Importierte Zeithistorie im Bericht öffnen** setzt Workspace und Datumsfilter direkt auf den übernommenen historischen Zeitraum. So siehst du alte Arbeit sofort, obwohl Berichte normalerweise mit dem aktuellen Monat beginnen.

Im Bericht lassen sich auch historische ClickUp-Personen einzeln filtern. Ticketkarten, Team-, Projekt-, Ticket- und Tagesauswertungen verwenden die exakte Dauer. CSV enthält zusätzlich **Dauer (ms)**, **Quelle**, **Quell-ID** und **Originalperson**; Minuten können bei importierten Buchungen Nachkommastellen enthalten.

Alle lokalen Änderungen eines Durchlaufs werden atomar gespeichert. Wiederholte Importe erzeugen keine doppelten Tickets oder Zeitbuchungen. Vorhandene lokale Tickets bleiben unverändert, neue Quellbuchungen können ergänzt werden. Die ursprünglichen Aufgaben und Zeiten in ClickUp bleiben erhalten. Kommentare, Anhänge, Custom Fields, ClickUp-spezifische Aufgabentypen und laufende Synchronisierung gehören nicht zum Import.

## Über MCP

Die Verbindung vorzugsweise im Dashboard einrichten, damit der Token nicht im Chat oder in MCP-Client-Protokollen landet.

1. `get_clickup_connection`: Verbindungsstatus lesen.
2. `list_clickup_locations`: ClickUp-Workspace, Space, Ordner und Listen wählen.
3. `preview_clickup`: Aufgaben einer Liste anzeigen, optional nur abgeschlossene.
4. `prepare_clickup_import`: Bis zu 20 Task-IDs und `team_id` prüfen, einschließlich aller verfügbaren historischen Einzelbuchungen.
5. `import_clickup`: Den zurückgegebenen `batch_id` im selben Ziel-Workspace übernehmen.

`configure_clickup` ist zusätzlich als ausschließlich schreibbarer Verbindungseinstieg verfügbar. Historische Personen ohne Konto haben in Zeitberichten negative Personen-IDs. Diese IDs aus `get_time_report` lesen und bei `user_id` unverändert verwenden; Tasklane-Konto-IDs bleiben positiv. Beispiel: „Prüfe diese abgeschlossenen ClickUp-Aufgaben mit ihrer gesamten Zeithistorie, übernimm sie nach GroupFractal und zeige anschließend die Zeit pro ursprünglicher Person im importierten Zeitraum.“
