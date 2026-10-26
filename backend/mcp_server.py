"""Lokaler Tasklane-MCP-Server (stdio). Der Host startet diesen Prozess pro Verbindung."""
import argparse
import asyncio
import json
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

from modules.work.services import OPERATIONS, WorkError, execute


def create_server(user_email=None):
    async def list_tools(context, params):
        allowed = set(OPERATIONS)
        if user_email is None:
            from modules.work.remote_mcp import remote_token
            from modules.work.token_auth import authenticate_token, action_allowed
            raw = remote_token.get()
            def available():
                close_old_connections()
                try:
                    grant = authenticate_token(raw)
                    return {name for name in OPERATIONS if action_allowed(grant, name)}
                finally: connections.close_all()
            allowed = await sync_to_async(available, thread_sensitive=True)()
        return ListToolsResult(tools=[Tool(
            name=name, description=op['description'], inputSchema=op['inputSchema'],
            annotations=ToolAnnotations(
                readOnlyHint=not op['write'],
                destructiveHint=op['write'] and not name.startswith(('create_', 'add_')),
                openWorldHint=bool(op.get('external')),
            ),
        ) for name, op in OPERATIONS.items() if name in allowed])

    async def call_tool(context, params):
        def run():
            close_old_connections()
            try:
                # Identität bei jedem Aufruf erneut prüfen: gesperrte Konten verlieren sofort Zugriff.
                if user_email is None:
                    from modules.work.remote_mcp import remote_token
                    from modules.work.token_auth import authenticate_token, execute_with_token
                    grant = authenticate_token(remote_token.get())
                    return execute_with_token(grant, params.name, params.arguments or {})
                user = get_user_model().objects.filter(email__iexact=user_email, is_active=True).first()
                return execute(user, params.name, params.arguments or {})
            finally:
                connections.close_all()
        try:
            result = await sync_to_async(run, thread_sensitive=True)()
            return CallToolResult(content=[TextContent(type='text', text=json.dumps(result, ensure_ascii=False))], structuredContent=result)
        except WorkError as error:
            return CallToolResult(content=[TextContent(type='text', text=str(error))], isError=True)

    from core.version import VERSION
    return Server(
        'tasklane', version=VERSION,
        instructions='Verwalte nur Projekte des konfigurierten Benutzers. Zuerst list_workspaces, list_projects und get_project/list_statuses lesen. Projekte gehören zu Workspaces; bei gleichen Kürzeln zuerst den Workspace klären. Jira- und ClickUp-Zugangsdaten vorzugsweise im Dashboard einrichten. ClickUp-Historie zuerst mit prepare_clickup_import prüfen; import_clickup übernimmt nur den geprüften Plan. Historische Personen-IDs aus get_time_report lesen; importierte Zeiten sind nur lesbar. Status-IDs, Mitglieder und Tags sind projektspezifisch und können sich ändern. Bei Änderungen erneut abrufen; keine Namen oder IDs raten. Epics haben keine Eltern; Tickets können Untertickets enthalten.',
        on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=lambda name: OPERATIONS.get(name, {}).get('inputSchema'),
    )


async def serve(user_email):
    server = create_server(user_email)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default=os.environ.get('TASKLANE_MCP_USER_EMAIL'), help='E-Mail eines bestehenden aktiven Tasklane-Kontos')
    args = parser.parse_args()
    if not args.user:
        parser.error('--user oder TASKLANE_MCP_USER_EMAIL ist erforderlich.')
    if not get_user_model().objects.filter(email__iexact=args.user, is_active=True).exists():
        print('Kein aktives Tasklane-Konto mit dieser E-Mail gefunden.', file=sys.stderr)
        sys.exit(1)
    asyncio.run(serve(args.user))
