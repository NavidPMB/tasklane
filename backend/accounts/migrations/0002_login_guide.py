from django.db import migrations


GUIDE = {'title': 'Bei Tasklane anmelden',
 'summary': 'Mit E-Mail und Passwort oder einem Google-Konto anmelden und die Sitzung beenden.',
 'body': '# Bei Tasklane anmelden\n'
         '\n'
         'Öffne `/login` und gib die E-Mail-Adresse und das Passwort deines Tasklane-Kontos ein. '
         'Nach **Anmelden** öffnet sich dein Dashboard. Du kannst dich am Computer und auf dem '
         'Handy auf dieselbe Weise anmelden.\n'
         '\n'
         'Ein Konto erhältst du von deiner Tasklane-Administration. Für ein bestehendes '
         'Google-Konto muss zuerst ein Passwort eingerichtet werden, bevor es auch die '
         'Passwortanmeldung verwenden kann. Wenn Google-Anmeldung für deine Umgebung aktiviert '
         'ist, erscheint zusätzlich **Mit Google anmelden**.\n'
         '\n'
         'Wenn die Anmeldung fehlschlägt, prüfe E-Mail-Adresse und Passwort. Nach mehreren '
         'fehlgeschlagenen Versuchen warte einige Minuten, bevor du es erneut versuchst. Bei einem '
         'gesperrten Konto oder einem vergessenen Passwort wende dich an deine Administration.\n'
         '\n'
         'Zum Abmelden verwende **Abmelden** im Bereichsmenü. Auf Mobilgeräten öffnest du das Menü '
         'über die Schaltfläche oben links.\n',
 'visibility': 'public',
 'is_published': True}


def seed_guide(apps, schema_editor):
    Article = apps.get_model('wiki', 'Article')
    Article.objects.get_or_create(slug='tasklane-anmelden', defaults=GUIDE)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial'), ('wiki', '0002_google_live_guide')]
    operations = [migrations.RunPython(seed_guide, migrations.RunPython.noop)]
