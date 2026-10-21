# Mit Tasklane arbeiten

## Projekte und Team

Zuerst unter **Dashboard → Workspaces & Team** einen Workspace erstellen oder einem geteilten Workspace beitreten. Danach unter **Dashboard → Projekte** ein Projekt im gewählten Workspace mit Namen und dauerhaftem Kürzel anlegen. Das Kürzel bildet die Ticketnummern, zum Beispiel `WEB-1`. Jedes Projekt hat einen eigenen Workflow, eigene Tags und eigene Mitglieder. Projektleitung, direkte Projektmitglieder und Mitglieder des übergeordneten Workspaces sehen das Projekt; Staff-Rechte allein geben keinen Zugriff auf fremde Projekte.

Die Projektleitung kann unter **Workflow & Team → Team & Projekt** bestehende aktive Konten anhand ihrer E-Mail hinzufügen. Neue Teammitglieder benötigen ein aktives Konto, das die Administration anlegen oder das über Google entstehen kann. Wird ein Mitglied entfernt, verliert es den Projektzugriff und seine Ticketzuweisungen in diesem Projekt werden gelöst. Die Projektleitung bleibt Mitglied.

## Epics, Tickets und Untertickets

**Epic** bündelt ein größeres Vorhaben. Mit **Ticket erstellen** eine Aufgabe anlegen und optional ein übergeordnetes Epic oder Ticket auswählen. Das Plus auf einer Boardkarte legt direkt ein Unterticket an. Untertickets können weitere Untertickets enthalten. Epics stehen auf der obersten Ebene.

Ein Ticket enthält Titel, Beschreibung, Status, Priorität, Fälligkeitsdatum, mehrere Zuständige und Tags. Zuweisungen sind auf aktive Projektmitglieder beschränkt. Mit einem Klick auf den Titel öffnet sich der Bearbeitungsdialog. Vor dem Löschen eines übergeordneten Tickets müssen seine Kinder umgehängt oder entfernt werden.

## Ein Workflow für alle Ansichten

Jedes Projekt startet mit vier Grundkategorien und je einem Grundstatus:

1. **Offen** – noch nicht begonnen.
2. **In Arbeit** – wird bearbeitet.
3. **Erledigt** – inhaltlich fertig.
4. **Geschlossen** – abschließend abgelegt.

Unter **Workflow & Team → Status** zusätzliche Status innerhalb dieser Kategorien anlegen, etwa „Review“ in „In Arbeit“. Die Position kann beim Anlegen gewählt und danach mit den Pfeilen geändert werden. Ein Status kann umbenannt werden; ein Zwischenstatus kann auch die Grundkategorie wechseln. Die vier Grundstatus bleiben bestehen.

Beim Entfernen eines Zwischenstatus einen Ersatzstatus wählen. Zugeordnete Tickets wechseln gemeinsam in diesen Ersatzstatus. Die Boardspalten, alle Statusauswahlen, Filter und MCP-Werkzeuge lesen dieselbe Liste.

Tickets per Drag-and-drop oder über ihre Statusauswahl verschieben. Die Auswahl funktioniert auch mit Tastatur und auf Mobilgeräten. **Liste & Hierarchie** zeigt die Eltern-Kind-Struktur. Suche und Filter lassen sich nach Status, Zuständigen, Tags, Epic und Tickettyp kombinieren. **Meine Tickets** filtert nach dem eigenen Konto.

## Tags und MCP

Tags unter **Workflow & Team → Tags** erstellen und im Ticketdialog auswählen. Umbenennen wirkt auf alle zugeordneten Tickets; Entfernen löst den Tag von den Tickets.

Unter **Dashboard → MCP-Anbindung** steht eine Konfiguration für lokale MCP-Clients. Der Assistent kann dieselben Projekte, Tickets, Tags und Status lesen und bearbeiten. Änderungen anderer Teammitglieder oder über MCP werden bei aktiver Seite alle zehn Sekunden und beim erneuten Fokussieren übernommen. Ein bereits geöffnetes Ticketformular überschreibt keine inzwischen gespeicherte Änderung; in diesem Fall das Ticket erneut öffnen.


Workspaces und Jira-Import: [Ausführliche Anleitung](workspaces-jira.md), auch unter `/wiki/tasklane-workspaces-jira`. Workspace-Mitglieder haben automatisch Zugriff auf alle aktuellen und künftigen Projekte. Unter **Jira-Import** lassen sich ausgewählte Jira-Cloud-Tickets inklusive automatisch angelegter Projekte übernehmen.
