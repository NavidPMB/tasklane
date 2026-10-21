"""Erzeugt eine lokale Konfiguration mit eigenen Secrets; bestehende Dateien bleiben erhalten."""
import argparse
import base64
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parent.parent
sample = (ROOT / ".env.example").read_text()
default_slug = re.search(r"^COMPOSE_PROJECT_NAME=(.+)$", sample, re.MULTILINE).group(1)
parser = argparse.ArgumentParser()
parser.add_argument("--slug", default=default_slug, help="Eigener Name für Datenbank und Docker-Projekt")
args = parser.parse_args()
if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", args.slug):
    parser.error("Der Slug muss mit a–z beginnen und darf nur a–z, 0–9 und _ enthalten (max. 48 Zeichen).")

target = ROOT / ".env"
if target.exists():
    if "CREDENTIAL_ENCRYPTION_KEY=" not in target.read_text():
        with target.open("a") as file:
            file.write("\nCREDENTIAL_ENCRYPTION_KEY=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() + "\n")
    print(".env ist bereits vorhanden und wurde beibehalten.")
else:
    content = sample
    content = content.replace("replace-with-a-random-secret", secrets.token_urlsafe(64))
    content = content.replace("replace-with-a-random-database-password", secrets.token_urlsafe(32))
    content = content.replace("replace-with-a-random-encryption-key", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    content = content.replace(default_slug, args.slug)
    with target.open("x") as file:
        target.chmod(0o600)
        file.write(content)
    print(".env mit eigenen lokalen Secrets erstellt.")
