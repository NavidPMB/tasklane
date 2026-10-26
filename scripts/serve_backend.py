import os
from pathlib import Path
import sys
import environ
root = Path(__file__).resolve().parent.parent
environ.Env.read_env(root / '.env')
os.chdir(root / 'backend')
os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'config.asgi:application', '--host', '127.0.0.1', '--port', os.environ.get('BACKEND_PORT', '8010'), '--reload', '--reload-dir', str(root / 'backend')])
