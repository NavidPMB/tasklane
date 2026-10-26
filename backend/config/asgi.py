import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_application = get_asgi_application()
from django.conf import settings
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    django_application = ASGIStaticFilesHandler(django_application)
from modules.work.remote_mcp import create_remote_app
mcp_application = create_remote_app()

async def application(scope, receive, send):
    if scope['type'] == 'lifespan' or (scope['type'] == 'http' and scope.get('path') in ('/mcp', '/mcp/')):
        if scope['type'] == 'http' and scope['path'] == '/mcp/':
            scope = {**scope, 'path': '/mcp', 'raw_path': b'/mcp'}
        await mcp_application(scope, receive, send)
    else:
        await django_application(scope, receive, send)
