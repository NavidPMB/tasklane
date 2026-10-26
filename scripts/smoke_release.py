"""Vollständiger HTTPS-Betriebstest in einer isolierten, anschließend gelöschten Testinstallation."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from uuid import uuid4

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import requests
import urllib3

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', default='tasklane-backend:standalone-test')
    parser.add_argument('--frontend-image', default='tasklane-frontend:standalone-test')
    parser.add_argument('--keep-on-failure', action='store_true', help='Testcontainer bei Fehlern für lokale Diagnose behalten.')
    args = parser.parse_args()
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    with tempfile.TemporaryDirectory(prefix='tasklane-release-smoke-') as folder:
        folder = Path(folder)
        folder.chmod(0o700)
        https_port, http_port = free_port(), free_port()
        base = f'https://localhost:{https_port}'
        name = 'tasklane-smoke-' + uuid4().hex[:10]
        env_file = folder / 'settings.env'
        config = {
            'COMPOSE_PROJECT_NAME': name, 'TASKLANE_DOMAIN': 'localhost',
            'TASKLANE_BIND_ADDRESS': '127.0.0.1', 'TASKLANE_HTTP_PORT': str(http_port), 'TASKLANE_HTTPS_PORT': str(https_port),
            'PUBLIC_URL': base, 'DJANGO_DEBUG': 'false', 'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1,backend',
            'DJANGO_CSRF_TRUSTED_ORIGINS': base, 'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
            'CREDENTIAL_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            'POSTGRES_DB': 'tasklane_smoke', 'POSTGRES_USER': 'tasklane', 'POSTGRES_PASSWORD': secrets.token_urlsafe(32),
        }
        env_file.write_text(''.join(f'{k}={v}\n' for k, v in config.items()));env_file.chmod(0o600)
        caddy = folder / 'Caddyfile'
        caddy.write_text((ROOT / 'deploy/Caddyfile').read_text().replace('{$TASKLANE_DOMAIN} {', '{$TASKLANE_DOMAIN} {\n    tls internal'))
        override = folder / 'compose.json'
        override.write_text(json.dumps({'services': {
            'backend': {'image': args.backend_image},
            'frontend': {'image': args.frontend_image, 'environment': {'PUBLIC_URL': base}},
            'proxy': {'volumes': [str(caddy) + ':/etc/caddy/Caddyfile:ro']},
        }}))
        env = {**os.environ, 'TASKLANE_ENV_FILE': str(env_file)}
        compose = ['docker', 'compose', '--project-name', name, '--env-file', str(env_file),
                   '-f', str(ROOT / 'compose.production.yaml'), '-f', str(override)]
        def run(*command, **kwargs):
            return subprocess.run([*compose, *command], env=env, cwd=ROOT, text=True, check=True, **kwargs)
        passed = False
        try:
            print('Starte isolierte Produktionsinstallation mit HTTPS, PostgreSQL und privaten Dateien.', flush=True)
            run('up', '-d', '--wait', '--wait-timeout', '180', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            password = secrets.token_urlsafe(24)
            code = 'from django.contrib.auth import get_user_model\nget_user_model().objects.create_superuser("smoke@example.test", password=' + repr(password) + ')\n'
            run('exec', '-T', 'backend', 'python', 'manage.py', 'shell', input=code, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            session = requests.Session();session.verify=False
            csrf = session.get(base+'/api/auth/session/',timeout=20).json()['csrfToken']
            login = session.post(base+'/api/auth/login/',json={'email':'smoke@example.test','password':password},headers={'Origin':base,'X-CSRFToken':csrf},timeout=20)
            assert login.status_code == 200, 'HTTPS login failed'
            csrf = session.get(base+'/api/auth/session/',timeout=20).json()['csrfToken']
            headers = {'Origin':base,'X-CSRFToken':csrf}
            def post(path, data):
                response=session.post(base+path,json=data,headers=headers,timeout=30)
                assert response.ok, f'{path}: HTTP {response.status_code}'
                return response.json()
            def action(name, data):return post('/api/work/actions/',{'action':name,'arguments':data})['result']
            workspace=action('create_workspace',{'name':'Release smoke'})
            project=action('create_project',{'workspace_id':workspace['id'],'name':'Production','key':'PROD'})
            common={'project_id':project['id']}
            action('create_custom_field',{**common,'key':'release','name':'Release','kind':'text'})
            ticket=action('create_ticket',{**common,'title':'HTTPS ticket','custom_fields':{'release':'0.2.0'}})
            ticket_args={**common,'ticket_id':ticket['id']}
            comment=action('create_comment',{**ticket_args,'body':'**Production comment**'})
            checklist=action('create_checklist',{**ticket_args,'name':'Smoke checks'})
            action('create_checklist_item',{**ticket_args,'checklist_id':checklist['id'],'title':'HTTPS login','done':True})
            payload=b'Tasklane private upload\n'*10000
            response=session.post(base+f"/api/work/projects/{project['id']}/tickets/{ticket['id']}/attachments/",files={'file':('private.txt',payload,'text/plain')},data={'comment_id':comment['id']},headers=headers,timeout=60)
            assert response.status_code == 201, f'Private upload failed: {response.status_code}'
            attachment=response.json()['result']
            assert attachment['sha256'] == hashlib.sha256(payload).hexdigest()
            assert session.get(base+attachment['download_url'],timeout=20).content == payload
            assert requests.get(base+attachment['download_url'],verify=False,timeout=20).status_code == 401
            assert session.get(base+'/dashboard',timeout=20).status_code == 200
            print('HTTPS-Anmeldung, Oberfläche, Ticket, Kommentar, Checkliste, Felder und private Datei: OK.',flush=True)
            token=post('/api/work/access-tokens/',{'name':'Smoke MCP','scope':'write','workspace_id':workspace['id'],'expires_in_days':1})
            bearer={'Authorization':'Bearer '+token['token']}
            assert requests.get(base+'/api/v1/projects',headers=bearer,verify=False,timeout=20).json()['projects'][0]['id']==project['id']
            async def mcp():
                async with httpx2.AsyncClient(headers=bearer,verify=False) as http:
                    async with Client(streamable_http_client(base+'/mcp',http_client=http),cache=None) as client:
                        snapshot=await client.call_tool('get_ticket',ticket_args)
                        assert not snapshot.is_error
                        assert snapshot.structured_content['custom_fields']['release']=='0.2.0'
                        part=await client.call_tool('read_attachment_chunk',{**common,'attachment_id':attachment['id'],'max_bytes':32})
                        assert base64.b64decode(part.structured_content['data_base64'])==payload[:32]
                        comment=await client.call_tool('create_comment',{**ticket_args,'body':'Remote MCP through real HTTPS'})
                        assert not comment.is_error
            asyncio.run(mcp())
            post('/api/work/access-tokens/',{'revoke_id':token['id']})
            assert requests.get(base+'/api/v1/projects',headers=bearer,verify=False,timeout=20).status_code==401
            print('Versionierte API, Remote-MCP über HTTPS und sofortiger Schlüsselwiderruf: OK.',flush=True)
            run('restart','backend','frontend',stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            deadline=time.monotonic()+60
            while True:
                try:
                    response=session.get(base+'/api/health/',timeout=5)
                    if response.ok:break
                except requests.RequestException:pass
                if time.monotonic()>deadline:raise AssertionError('Restart health check timed out')
                time.sleep(.5)
            assert session.get(base+attachment['download_url'],timeout=20).content==payload
            assert session.get(base+'/api/auth/session/',timeout=20).json()['authenticated']
            assert session.get(base+'/api/health/',timeout=20).json()['version']==(ROOT/'VERSION').read_text().strip()
            print('Neustart: Sitzung, Datenbank und private Anhänge bleiben erhalten. Release-Smoke-Test erfolgreich.',flush=True)
            passed=True
        except subprocess.CalledProcessError as error:
            print('Container-Befehl fehlgeschlagen: ' + (error.stderr or '')[-3000:],flush=True)
            raise RuntimeError('Production smoke test failed') from None
        finally:
            if passed or not args.keep_on_failure:
                run('down','--volumes','--remove-orphans',stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            else:
                print('Testcontainer behalten: '+name,flush=True)


if __name__ == '__main__': main()
