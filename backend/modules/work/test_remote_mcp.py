import asyncio
import base64
from contextlib import contextmanager
import socket
import tempfile
from threading import Thread
import time

from asgiref.sync import async_to_sync, sync_to_async
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, override_settings
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
import requests
import uvicorn

from .services import execute
from .token_auth import create_token, revoke_token


class RemoteMcpTests(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('remote-owner@example.test')
        self.other=get_user_model().objects.create_user('remote-other@example.test')
        self.project=execute(self.user,'create_project',{'name':'Remote','key':'REM'})
        self.private=execute(self.other,'create_project',{'name':'Other','key':'OTH'})
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)

    @contextmanager
    def server(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        with override_settings(PUBLIC_URL=url,DEBUG=True,ALLOWED_HOSTS=['127.0.0.1','localhost','testserver'],INTEGRATION_ALLOWED_ORIGINS=[url],PRIVATE_FILE_ROOT=self.directory.name):
            from .remote_mcp import create_remote_app
            app=create_remote_app()
            server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',lifespan='on'))
            thread=Thread(target=server.run,daemon=True);thread.start()
            deadline=time.monotonic()+5
            while not server.started:
                if time.monotonic()>deadline:raise RuntimeError('Remote MCP test server failed to start')
                time.sleep(.02)
            try:yield url
            finally:
                server.should_exit=True;thread.join(5)
                self.assertFalse(thread.is_alive())

    def test_sdk_http_tickets_collaboration_and_binary_roundtrip(self):
        with self.server() as url:
            token=create_token(self.user,'Remote',scope='write')['token']
            async def exercise():
                async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token}) as http:
                    async with Client(streamable_http_client(url+'/mcp',http_client=http),cache=None) as client:
                        tools=await client.list_tools();self.assertIn('create_checklist_item',{t.name for t in tools.tools})
                        ticket=await client.call_tool('create_ticket',{'project_id':self.project['id'],'title':'Created over HTTP'})
                        self.assertFalse(ticket.is_error)
                        ticket_id=ticket.structured_content['id']
                        comment=await client.call_tool('create_comment',{'project_id':self.project['id'],'ticket_id':ticket_id,'body':'Remote comment'})
                        self.assertFalse(comment.is_error)
                        checklist=await client.call_tool('create_checklist',{'project_id':self.project['id'],'ticket_id':ticket_id,'name':'Remote checklist'})
                        item=await client.call_tool('create_checklist_item',{'project_id':self.project['id'],'ticket_id':ticket_id,'checklist_id':checklist.structured_content['id'],'title':'Test','done':True})
                        self.assertFalse(item.is_error)
                        upload=await client.call_tool('start_attachment_upload',{'project_id':self.project['id'],'ticket_id':ticket_id,'filename':'remote.txt','size':5})
                        attachment_id=upload.structured_content['id']
                        block=await client.call_tool('put_attachment_chunk',{'project_id':self.project['id'],'attachment_id':attachment_id,'offset':0,'data_base64':base64.b64encode(b'hello').decode()})
                        self.assertFalse(block.is_error)
                        complete=await client.call_tool('complete_attachment_upload',{'project_id':self.project['id'],'attachment_id':attachment_id})
                        self.assertFalse(complete.is_error)
                        data=await client.call_tool('read_attachment_chunk',{'project_id':self.project['id'],'attachment_id':attachment_id})
                        self.assertEqual(base64.b64decode(data.structured_content['data_base64']),b'hello')
                        outside=await client.call_tool('get_project',{'project_id':self.private['id']});self.assertTrue(outside.is_error)
            async_to_sync(exercise)()

    def test_read_only_discovery_auth_origin_and_immediate_revocation(self):
        with self.server() as url:
            token=create_token(self.user,'Read',scope='read')
            self.assertEqual(requests.post(url+'/mcp',json={}).status_code,401)
            self.assertEqual(requests.post(url+'/mcp',json={},headers={'Authorization':'Bearer '+token['token'],'Origin':'https://evil.example'}).status_code,403)
            async def exercise():
                async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token['token']}) as http:
                    async with Client(streamable_http_client(url+'/mcp',http_client=http),cache=None) as client:
                        names={t.name for t in (await client.list_tools()).tools}
                        self.assertIn('get_project',names);self.assertNotIn('create_ticket',names)
                        denied=await client.call_tool('create_ticket',{'project_id':self.project['id'],'title':'Denied'})
                        self.assertTrue(denied.is_error)
            async_to_sync(exercise)()
            revoke_token(self.user,token['id'])
            self.assertEqual(requests.post(url+'/mcp',json={},headers={'Authorization':'Bearer '+token['token']}).status_code,401)

    def test_concurrent_http_identities_remain_isolated(self):
        with self.server() as url:
            first=create_token(self.user,'First',scope='read')['token']
            second=create_token(self.other,'Second',scope='read')['token']
            async def projects(token):
                async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token}) as http:
                    async with Client(streamable_http_client(url+'/mcp',http_client=http),cache=None) as client:
                        response=await client.call_tool('list_projects',{})
                        return [p['id'] for p in response.structured_content['projects']]
            async def exercise():return await asyncio.gather(projects(first),projects(second))
            self.assertEqual(async_to_sync(exercise)(),[[self.project['id']],[self.private['id']]])
