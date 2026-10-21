# Workspaces teilen und Jira-Tickets importieren

## Workspace und Team vorbereiten

Öffne **Dashboard → Workspaces & Team**, erstelle zum Beispiel **GroupFractal** und füge Sina über seine E-Mail hinzu. Die Person benötigt bereits ein aktives Tasklane-Konto; ein Administrator kann es unter **Benutzer** anlegen. Es wird keine Einladung per E-Mail versendet.

Workspace-Mitglieder können auf **alle bestehenden und zukünftigen Projekte** dieses Workspaces zugreifen, Tickets bearbeiten, Zeit buchen und neue Projekte erstellen. Ein Workspace kann beispielsweise 20 Projekte enthalten; es gibt keine feste Projektgrenze. Die Workspace-Leitung verwaltet die Freigabe und die Jira-Verbindung. Sie kann außerdem die Projekteinstellungen aller Projekte ihres Workspaces ändern.

Zusätzliche Freigaben unter **Workflow & Team** gelten nur für das jeweilige Projekt. Solche Projektgäste sehen keine anderen Projekte und nicht das Workspace-Team oder die Jira-Zugangsdaten. Beim Entfernen einer Workspace-Mitgliedschaft bleiben separate Projektfreigaben und die Leitung eigener Projekte erhalten. Ticketzuweisungen werden dort entfernt, wo der Projektzugriff endet; gebuchte Zeiten bleiben für die Berichte erhalten.

Bestehende Projekte werden beim Upgrade je Projektleitung in **Meine Projekte** eingeordnet. Ihre bisherigen Projektfreigaben bleiben unverändert. Dadurch werden private Projekte nicht automatisch für die Mitglieder anderer Projekte sichtbar.

Unter **Board & Tickets** und **Projekte** grenzt die Workspace-Auswahl die sichtbaren Projekte ein. Neue Projekte werden im gewählten Workspace angelegt. In **Zeiten & Berichte** kannst du ebenfalls nach Workspace filtern.

## Jira Cloud verbinden

1. Öffne **Jira-Import** und wähle den Ziel-Workspace, zum Beispiel GroupFractal.
2. Trage die Jira-Cloud-Adresse wie `https://dein-team.atlassian.net`, deine Jira-E-Mail und einen eigenen API-Token ein.
3. Klicke auf **Verbindung prüfen & speichern**. Erst nach erfolgreicher Prüfung werden die Zugangsdaten gespeichert.

Tokens mit und ohne Scopes werden unterstützt. Für Tokens mit Scopes benötigt das Jira-Konto die passenden Lese-Scopes für das eigene Profil und die Tickets sowie die Berechtigung zum Lesen der betreffenden Projekte. Die klassischen Scopes `read:jira-user` und `read:jira-work` decken diese REST-Aufrufe ab. Bei granularen Scopes die Anforderungen der verlinkten Atlassian-Endpunkte beachten. Ein Token erweitert die Projektberechtigungen des Jira-Kontos nicht.

[API-Token erstellen und verwalten](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/), [Jira-Profil-API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-myself/), [Jira-Suche](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/).

Der Token wird zentral verschlüsselt auf dem Server gespeichert. Er wird nicht zurückgegeben und nicht im Browser-Speicher abgelegt. Nur die Workspace-Leitung kann die Verbindung prüfen, ändern und für Importe verwenden. Einen neuen Token kannst du über dasselbe Formular hinterlegen. Nach einem Import bleibt die Jira-Site dieser Verbindung fest; für eine andere Site einen neuen Workspace anlegen.

Diese Verbindung ist für Jira Cloud unter `*.atlassian.net` vorgesehen. Selbst gehostete Jira-Server und eigene Cloud-Domains werden nicht unterstützt.

## Vorschau und Auswahl

Gib eine JQL-Suche ein, zum Beispiel:

```text
project in (WEB, APP) ORDER BY updated DESC
```

Oder für deine eigenen Tickets:

```text
assignee = currentUser() ORDER BY updated DESC
```

**Vorschau laden** zeigt Schlüssel, Titel, Projekt, Status, Typ und Eltern-Ticket. **Weitere Tickets laden** lädt die nächste Seite. Wähle bis zu **50 Tickets pro Import**; du kannst anschließend weitere importieren. Die Auswahl darf mehrere Jira-Projekte umfassen. Bereits importierte Tickets sind markiert und werden übersprungen.

**Tickets importieren** legt die benötigten Projekte automatisch im gewählten Workspace an. Eine reine Vorschau erstellt keine Projekte. Existiert ein Projektkürzel bereits und gehört zu einem anderen lokalen Projekt, erhält das neue Importprojekt ein freies Kürzel. Das vorhandene Projekt bleibt erhalten. Derselbe Jira-Quellprojektbezug wird bei weiteren Importen wiederverwendet.

## Was übernommen wird

- Titel und Beschreibung als Klartext; Jira-Formatierung wird vereinfacht.
- Epic bzw. Ticket, Priorität und Fälligkeitsdatum.
- Jira-Status als lokale Status. Die vier Grundkategorien bleiben erhalten; zusätzliche Status erscheinen im Board, in Dropdowns und über MCP.
- Jira-Labels als Tags.
- Zuweisungen, wenn Jira eine E-Mail liefert und diese zu einem aktiven Mitglied des Zielprojekts gehört. Andernfalls bleibt das Ticket unzugewiesen und der Import nennt einen Hinweis.
- Elternbeziehungen innerhalb desselben Projekts, wenn das Eltern-Ticket in derselben Auswahl oder bereits importiert ist. Nicht auflösbare Beziehungen werden als Hinweis gemeldet. Wähle Epics und Eltern-Tickets deshalb ebenfalls aus.
- Ein Link zum ursprünglichen Jira-Ticket in den Ticketdetails.

Tasklane vergibt eigene lokale Ticketnummern. Der ursprüngliche Jira-Schlüssel bleibt über den Quellverweis erreichbar. Titel, Projekt- und Statusnamen, Tags und Beschreibungen werden auf die lokalen Feldlängen begrenzt.

Der Import ist eine **einmalige Übernahme**, keine laufende Synchronisation. Wiederholte Importe überspringen bereits vorhandene Quell-Tickets und überschreiben lokale Änderungen nicht. Werden Eltern erst später importiert, kannst du bereits importierte Kinder anschließend manuell zuordnen. Kommentare, Anhänge, Jira-Worklogs, Sprints und Jira-Benutzerkonten werden nicht importiert.

Ein Import speichert seine Auswahl atomar. Sind nicht alle ausgewählten Tickets zugänglich oder schlagen lokale Prüfungen fehl, wird nichts aus diesem Durchlauf gespeichert. Lade nach einem Fehler die Vorschau neu und versuche es erneut. Die Ergebnisse zeigen neue Projekte, importierte oder übersprungene Tickets und Hinweise zur Zuordnung.

## Mit MCP arbeiten

Workspace-Werkzeuge: `list_workspaces`, `create_workspace`, `get_workspace`, `update_workspace`, `add_workspace_member`, `remove_workspace_member`.

`create_project` nimmt `workspace_id` an; ohne diese ID verwendet es einen persönlichen Workspace. `list_projects`, `get_time_report`, `list_time_entries` und `export_time_report` können über `workspace_id` eingegrenzt werden. Projektkürzel sind nur innerhalb eines Workspaces eindeutig: Bei gleichen Kürzeln immer Workspace und Projekt-ID klären.

Jira-Werkzeuge: `get_jira_connection`, `configure_jira`, `preview_jira`, `import_jira`. Zugangsdaten vorzugsweise im Dashboard einrichten, damit sie nicht in Chatverläufen oder MCP-Client-Protokollen landen. Danach zum Beispiel: „Zeige Jira-Tickets für `project = WEB` im Workspace GroupFractal und importiere WEB-1 sowie WEB-2.“ Der Assistent muss die Auswahl und den Ziel-Workspace aus dem Auftrag ableiten; das Importwerkzeug nimmt nur Ticket-Schlüssel an und liest die Quelldaten selbst erneut aus Jira.
