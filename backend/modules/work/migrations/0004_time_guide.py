from django.db import migrations


GUIDE = {'title': 'Arbeitszeit buchen und auswerten',
 'summary': 'Zeit auf Tickets buchen, eigene Buchungen korrigieren und Teamberichte als CSV '
            'exportieren.',
 'body': '# Arbeitszeit buchen und Berichte lesen\n'
         '\n'
         '## Arbeitszeit auf ein Ticket buchen\n'
         '\n'
         'Öffne ein bestehendes Ticket oder Epic und wähle **Zeit erfassen**. Gib das '
         'Arbeitsdatum, die Dauer in Stunden und Minuten und optional eine Notiz an. Mit **Zeit '
         'buchen** wird die Dauer deinem angemeldeten Konto zugeordnet. Neue Tickets müssen zuerst '
         'gespeichert werden.\n'
         '\n'
         'Eine Buchung enthält zwischen einer Minute und 24 Stunden. Arbeitszeit kann für heute '
         'oder einen vergangenen Tag erfasst werden. Mehrere Buchungen auf demselben Ticket sind '
         'möglich. Das Board und die Listenansicht zeigen die insgesamt auf dem jeweiligen Ticket '
         'gebuchte Arbeitszeit.\n'
         '\n'
         'Die Erfassung erfolgt manuell; es wird keine laufende Stoppuhr gestartet. Zeiten eines '
         'Untertickets werden nur diesem Ticket zugerechnet und nicht nochmals beim übergeordneten '
         'Epic addiert.\n'
         '\n'
         '## Eigene Buchungen korrigieren\n'
         '\n'
         'Unter **Zeit erfassen** siehst du die Buchungen auf dem Ticket. Bei eigenen Buchungen '
         'stehen **Bearbeiten** und **Löschen** zur Verfügung. Datum, Dauer und Notiz können '
         'korrigiert werden. Andere Personen können deine Buchungen lesen, sofern sie Zugriff auf '
         'das Projekt haben, aber nicht verändern – auch die Projektleitung nicht.\n'
         '\n'
         'Tickets mit Zeitbuchungen können geschlossen, aber nicht gelöscht werden. Buchungen '
         'bleiben auch dann im Projektbericht erhalten, wenn die betreffende Person das Projekt '
         'verlässt oder ihr Konto deaktiviert wird. Nach dem Entfernen aus einem Projekt besteht '
         'kein Zugriff mehr auf dessen Buchungen und Berichte.\n'
         '\n'
         '## Berichte erstellen\n'
         '\n'
         'Öffne **Zeiten & Berichte** im Bereichsmenü. Standardmäßig werden alle Projekte, auf die '
         'du Zugriff hast, vom Monatsanfang bis heute ausgewertet. Wähle ein einzelnes Projekt, '
         'eine Person und einen Zeitraum oder verwende **Heute**, **Diese Woche** und **Dieser '
         'Monat**. Die Grenztage zählen mit.\n'
         '\n'
         'Der **Teambericht** zeigt die gesamte gebuchte Zeit sowie Summen pro Person, Projekt, '
         'Ticket und Tag. Bei Personen werden außerdem Buchungen und Arbeitstage angezeigt. Ein '
         'Arbeitstag ist ein Kalendertag mit mindestens einer Buchung. Die Zeiten werden der '
         'buchenden Person zugerechnet; eine Ticketzuweisung allein erzeugt keine Arbeitszeit.\n'
         '\n'
         '**Einzelne Buchungen** zeigt Datum, Person, Projekt, Ticket, Dauer und Notiz. Eigene '
         'Buchungen können von hier aus ebenfalls bearbeitet werden. **CSV exportieren** lädt alle '
         'Buchungen passend zu den gewählten Filtern herunter, einschließlich der Einträge auf '
         'weiteren Seiten. Die Datei verwendet UTF-8 und Semikolon als Trennzeichen.\n'
         '\n'
         'Die Ansicht übernimmt Änderungen anderer Teammitglieder oder MCP-Clients alle zehn '
         'Sekunden bei aktiver Seite und beim erneuten Fokussieren des Fensters.\n'
         '\n'
         '## Über MCP arbeiten\n'
         '\n'
         'Beispiele für den Assistenten:\n'
         '\n'
         '- „Buche heute 90 Minuten Entwicklung auf WEB-3.“\n'
         '- „Wie viel Arbeitszeit hat jede Person in diesem Monat gebucht?“\n'
         '- „Zeige die Zeiten für Projekt WEB vom 1. bis 15. des Monats.“\n'
         '- „Korrigiere meine Buchung auf 75 Minuten.“\n'
         '- „Exportiere den gefilterten Zeitbericht als CSV.“\n'
         '\n'
         'Die zugehörigen Werkzeuge heißen `create_time_entry`, `update_time_entry`, '
         '`delete_time_entry`, `list_time_entries`, `get_time_report` und `export_time_report`. '
         'Datum wird als `JJJJ-MM-TT`, Dauer als ganze `minutes` angegeben. Die Buchung gehört '
         'immer dem Konto, mit dem der MCP-Prozess verbunden ist.\n',
 'visibility': 'registered',
 'is_published': True}


def seed_guide(apps, schema_editor):
    Article = apps.get_model('wiki', 'Article')
    Article.objects.get_or_create(slug='tasklane-arbeitszeit', defaults=GUIDE)


class Migration(migrations.Migration):
    dependencies = [('work', '0003_timeentry'), ('wiki', '0002_google_live_guide')]
    operations = [migrations.RunPython(seed_guide, migrations.RunPython.noop)]
