"""SDK-Streamable-HTTP mit statischen persönlichen Bearer-Schlüsseln."""
from contextvars import ContextVar
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections, connections
from django.http.request import validate_host
from starlette.responses import JSONResponse
from mcp.server.transport_security import TransportSecuritySettings

from .errors import WorkError
from .token_auth import authenticate_token

remote_token = ContextVar('tasklane_remote_token', default=None)


def create_remote_app():
    from mcp_server import create_server
    host = urlsplit(settings.PUBLIC_URL).netloc
    allowed_hosts = [host] + (['localhost:*', '127.0.0.1:*', 'testserver'] if settings.DEBUG else [])
    transport = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed_hosts,
                                        allowed_origins=settings.INTEGRATION_ALLOWED_ORIGINS)
    sdk_app = create_server(None).streamable_http_app(stateless_http=True, json_response=True,
                max_request_body_size=settings.DATA_UPLOAD_MAX_MEMORY_SIZE, transport_security=transport, host=host)

    async def app(scope, receive, send):
        if scope['type'] == 'lifespan':
            await sdk_app(scope, receive, send); return
        if scope['type'] != 'http':
            return
        headers = {}
        duplicate_auth = False
        for key, value in scope.get('headers', []):
            name = key.decode().lower()
            if name == 'authorization' and name in headers: duplicate_auth = True
            headers[name] = value.decode('latin1')
        try:
            if not settings.DEBUG and scope.get('scheme') != 'https' and headers.get('x-forwarded-proto') != 'https':
                raise WorkError('HTTPS erforderlich.', 400)
            if headers.get('origin') and headers['origin'].rstrip('/') not in settings.INTEGRATION_ALLOWED_ORIGINS:
                raise WorkError('Origin nicht zugelassen.', 403)
            incoming_host = headers.get('host', '').split(':')[0].lower()
            if not validate_host(incoming_host, settings.ALLOWED_HOSTS): raise WorkError('Host nicht zugelassen.', 400)
            auth = headers.get('authorization', '')
            if duplicate_auth or not auth.startswith('Bearer '): raise WorkError('Bearer-Schlüssel erforderlich.', 401)
            raw = auth[7:]
            def verify():
                close_old_connections()
                try: authenticate_token(raw)
                finally: connections.close_all()
            await sync_to_async(verify, thread_sensitive=True)()
        except WorkError as error:
            response = JSONResponse({'error': str(error)}, status_code=error.status,
                        headers={'WWW-Authenticate': 'Bearer realm="tasklane"', 'Cache-Control': 'no-store'})
            await response(scope, receive, send); return
        token = remote_token.set(raw)
        try:
            await sdk_app(scope, receive, send)
        finally:
            remote_token.reset(token)
    return app
