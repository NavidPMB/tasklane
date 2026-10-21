import os
from pathlib import Path
import sys

import environ

root = Path(__file__).resolve().parent.parent
environ.Env.read_env(root / ".env")
os.execv(sys.executable, [sys.executable, str(root / "backend/manage.py"), "runserver", f"127.0.0.1:{os.environ.get('BACKEND_PORT', '8002')}"])
