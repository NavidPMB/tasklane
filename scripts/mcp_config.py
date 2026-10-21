"""Print a stdio MCP configuration with absolute paths for this checkout."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing active Tasklane account")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not email or "@" not in email:
        parser.error("Set MCP_EMAIL to your Tasklane email, e.g. make mcp-config MCP_EMAIL=you@example.com")
    print(json.dumps({"mcpServers": {"tasklane": {
        "command": str(ROOT / ".venv/bin/python"),
        "args": [str(ROOT / "backend/mcp_server.py")],
        "env": {"TASKLANE_MCP_USER_EMAIL": email},
    }}}, indent=2))


if __name__ == "__main__":
    main()
