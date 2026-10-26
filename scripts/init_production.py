"""Erzeugt private, unabhängige Einstellungen für eine eigene HTTPS-Domain."""
import argparse
import base64
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True, help='Zum Beispiel tasks.example.com, ohne https://')
    parser.add_argument('--output', default='.env.production')
    args = parser.parse_args()
    domain = args.domain.lower().strip()
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
        parser.error('Bitte einen gültigen DNS-Domainnamen ohne Pfad oder Port angeben.')
    path = Path(args.output)
    if path.exists(): parser.error(f'{path} existiert bereits und wird nicht überschrieben.')
    version = (Path(__file__).resolve().parent.parent / 'VERSION').read_text().strip()
    values = {
        'COMPOSE_PROJECT_NAME': 'tasklane-production', 'TASKLANE_DOMAIN': domain, 'TASKLANE_VERSION': version,
        'PUBLIC_URL': 'https://' + domain, 'DJANGO_DEBUG': 'false',
        'DJANGO_ALLOWED_HOSTS': domain + ',backend,localhost,127.0.0.1',
        'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://' + domain,
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
        'CREDENTIAL_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'POSTGRES_DB': 'tasklane', 'POSTGRES_USER': 'tasklane', 'POSTGRES_PASSWORD': secrets.token_urlsafe(40),
        'BACKEND_URL': 'http://backend:8010', 'ATTACHMENT_MAX_BYTES': '52428800',
        'ATTACHMENT_TICKET_MAX_BYTES': '1073741824',
    }
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    print(f'{path} mit privaten Einstellungen für https://{domain} angelegt. Bestehende lokale Daten bleiben unberührt.')


if __name__ == '__main__': main()
