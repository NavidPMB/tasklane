"""Verify MCP initialization, tool discovery and a read-only call over stdio."""
import argparse
import asyncio
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent


async def check(email):
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "backend/mcp_server.py"), "--user", email],
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        result = await client.call_tool("list_projects", {})
        if result.is_error:
            raise RuntimeError("list_projects failed. Check the account and database configuration.")
        projects = result.structured_content["projects"]
        print(f"MCP OK: {len(tools.tools)} tools discovered, {len(projects)} accessible projects.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing active Tasklane account")
    args = parser.parse_args()
    if not args.email.strip() or "@" not in args.email:
        parser.error("Set MCP_EMAIL to your Tasklane email, e.g. make mcp-check MCP_EMAIL=you@example.com")
    asyncio.run(check(args.email.strip().lower()))


if __name__ == "__main__":
    main()
