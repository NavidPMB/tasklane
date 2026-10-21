from django.db import migrations


def seed_google(apps, schema_editor):
    apps.get_model("integrations", "IntegrationCredential").objects.get_or_create(
        key="google", defaults={"name": "Google Login", "kind": "oauth2", "enabled": False},
    )


class Migration(migrations.Migration):
    dependencies = [("integrations", "0001_initial")]
    operations = [migrations.RunPython(seed_google, migrations.RunPython.noop)]
