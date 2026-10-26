"""Aktualisiert ausschließlich unveränderte Ausgangsfassungen der Dienstanleitungen."""
from importlib import import_module

from django.db import migrations


def update_guides(apps, schema_editor):
    Article = apps.get_model('wiki', 'Article')
    originals = import_module('modules.work.migrations.0012_standalone_guides').GUIDES
    replacements = {
        'tasklane-betrieb': [
            ('git clone --branch v0.2.0', 'git clone --branch v0.2.1'),
            ('](api.md)', '](/wiki/tasklane-api-mcp)'),
        ],
        'tasklane-dienst-entwicklung': [
            ('](../production.md)', '](/wiki/tasklane-betrieb)'),
            ('Entwicklung über Uvicorn mit Reload;', 'Entwicklung über Uvicorn mit Reload und Djangos Staticfiles-ASGI-Handler bei `DEBUG`;'),
        ],
    }
    for guide in originals:
        if guide['slug'] not in replacements:
            continue
        body = guide['body']
        for old, new in replacements[guide['slug']]:
            body = body.replace(old, new)
        Article.objects.filter(slug=guide['slug'], body=guide['body']).update(body=body)


class Migration(migrations.Migration):
    dependencies = [('work', '0012_standalone_guides')]
    operations = [migrations.RunPython(update_guides, migrations.RunPython.noop)]
