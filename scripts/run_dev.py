"""Run the local backend and frontend together; Ctrl+C stops both process groups."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import environ

ROOT = Path(__file__).resolve().parent.parent


def main():
    environ.Env.read_env(ROOT / ".env")
    stopping = False
    children = []

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        children.append(subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/serve_backend.py")],
            cwd=ROOT, start_new_session=True,
        ))
        children.append(subprocess.Popen(
            ["npm", "run", "dev"], cwd=ROOT / "frontend", start_new_session=True,
        ))
        print(f"\nTasklane: {os.environ.get('PUBLIC_URL', 'http://localhost:3010')}\nCtrl+C stops the backend and frontend.\n", flush=True)
        while not stopping:
            for child in children:
                code = child.poll()
                if code is not None:
                    print("A development server exited; stopping the other server.", file=sys.stderr)
                    return code or 1
            time.sleep(0.2)
        return 0
    except OSError as error:
        print(f"Could not start Tasklane: {error}", file=sys.stderr)
        return 1
    finally:
        # Terminate process groups, including Django's reloader and Next.js children.
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for child in children:
            child.wait()


if __name__ == "__main__":
    sys.exit(main())
