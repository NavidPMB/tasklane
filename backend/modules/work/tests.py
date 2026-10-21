import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections, connections
from django.test import Client, TestCase, TransactionTestCase
from mcp import Client as McpClient
from mcp import StdioServerParameters

from .models import Project, Status, Ticket
from .services import OPERATIONS, WorkError, execute


class WorkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('owner@example.test')
        cls.member = User.objects.create_user('member@example.test')
        cls.outsider = User.objects.create_user('outside@example.test')
        cls.staff = User.objects.create_user('staff@example.test', is_staff=True)
        cls.project = execute(cls.owner, 'create_project', {'name': 'Website', 'key': 'WEB'})
        cls.other = execute(cls.outsider, 'create_project', {'name': 'Privat', 'key': 'PRV'})
        execute(cls.owner, 'add_project_member', {'project_id': cls.project['id'], 'email': cls.member.email})

    def action(self, action, user=None, **args):
        return execute(user or self.owner, action, {'project_id': self.project['id'], **args})

    def test_four_defaults_and_project_access(self):
        snapshot = self.action('get_project')
        self.assertEqual([s['category'] for s in snapshot['statuses']], ['open', 'in_progress', 'done', 'closed'])
        self.assertEqual(len([s for s in snapshot['statuses'] if s['is_base']]), 4)
        self.assertTrue(snapshot['project']['can_manage'])
        self.assertFalse(self.action('get_project', user=self.member)['project']['can_manage'])
        self.assertEqual([p['key'] for p in execute(self.member, 'list_projects', {})['projects']], ['WEB'])
        for user in [self.outsider, self.staff]:
            with self.assertRaises(WorkError) as cm:
                self.action('get_project', user=user)
            self.assertEqual(cm.exception.status, 404)

    def test_dynamic_status_used_by_tickets_and_snapshot(self):
        review = self.action('create_status', name='Review', category='in_progress')
        ticket = self.action('create_ticket', title='Prüfen', status_id=review['id'])
        self.assertEqual(ticket['status_id'], review['id'])
        self.action('update_status', status_id=review['id'], name='Code Review')
        snapshot = self.action('get_project', user=self.member)
        self.assertIn('Code Review', [s['name'] for s in snapshot['statuses']])
        self.assertEqual(snapshot['tickets'][0]['status_id'], review['id'])

    def test_status_insertion_and_reordering(self):
        a = self.action('create_status', name='Entwicklung', category='in_progress')
        b = self.action('create_status', name='Review', category='in_progress')
        c = self.action('create_status', name='Test', category='in_progress', position=a['position'] + 1)
        names = lambda: [s['name'] for s in self.action('list_statuses')['statuses'] if s['category'] == 'in_progress']
        self.assertEqual(names(), ['In Arbeit', 'Entwicklung', 'Test', 'Review'])
        self.action('update_status', status_id=b['id'], position=1)
        self.assertEqual(names(), ['In Arbeit', 'Review', 'Entwicklung', 'Test'])
        self.action('update_status', status_id=c['id'], category='done')
        snapshot = self.action('get_project')
        self.assertEqual(next(s['category'] for s in snapshot['statuses'] if s['id'] == c['id']), 'done')

    def test_base_status_protection_and_category_validation(self):
        status = self.action('list_statuses')['statuses'][0]
        for action, args in [('delete_status', {'status_id': status['id']}), ('update_status', {'status_id': status['id'], 'category': 'done'}), ('create_status', {'name': 'X', 'category': 'invalid'})]:
            with self.assertRaises(WorkError):
                self.action(action, **args)
        self.assertEqual(Status.objects.filter(project_id=self.project['id'], is_base=True).count(), 4)

    def test_delete_used_status_reassigns_atomically(self):
        custom = self.action('create_status', name='Review', category='in_progress')
        ticket = self.action('create_ticket', title='Behalten', status_id=custom['id'])
        with self.assertRaises(WorkError):
            self.action('delete_status', status_id=custom['id'])
        replacement = self.action('list_statuses')['statuses'][0]['id']
        self.action('delete_status', status_id=custom['id'], replacement_status_id=replacement)
        self.assertEqual(Ticket.objects.get(pk=ticket['id']).status_id, replacement)

    def test_hierarchy_assignees_tags_and_ticket_numbers(self):
        epic = self.action('create_ticket', title='Relaunch', kind='epic')
        tag = self.action('create_tag', name='Frontend')
        ticket = self.action('create_ticket', title='Startseite', parent_id=epic['id'], assignee_ids=[self.member.pk], tag_ids=[tag['id']], due_date='2026-12-01')
        sub = self.action('create_ticket', title='Navigation', parent_id=ticket['id'])
        self.assertEqual([epic['key'], ticket['key'], sub['key']], ['WEB-1', 'WEB-2', 'WEB-3'])
        self.assertEqual(ticket['assignee_ids'], [self.member.pk])
        self.assertEqual(ticket['tag_ids'], [tag['id']])
        self.assertEqual(sub['parent_id'], ticket['id'])
        self.action('update_ticket', ticket_id=ticket['id'], assignee_ids=[], tag_ids=[], due_date=None)
        updated = self.action('get_ticket', ticket_id=ticket['id'])
        self.assertEqual(updated['assignee_ids'], [])
        self.assertIsNone(updated['due_date'])

    def test_cycles_self_parent_and_epic_parent_rejected(self):
        parent = self.action('create_ticket', title='Parent')
        child = self.action('create_ticket', title='Child', parent_id=parent['id'])
        for args in [dict(ticket_id=parent['id'], parent_id=child['id']), dict(ticket_id=child['id'], parent_id=child['id']), dict(ticket_id=child['id'], kind='epic')]:
            with self.assertRaises(WorkError):
                self.action('update_ticket', **args)
        with self.assertRaises(WorkError):
            self.action('delete_ticket', ticket_id=parent['id'])
        self.action('update_ticket', ticket_id=child['id'], parent_id=None)
        self.action('delete_ticket', ticket_id=parent['id'])

    def test_cross_project_status_parent_tag_and_assignee_rejected(self):
        other_id = self.other['id']
        other_status = execute(self.outsider, 'list_statuses', {'project_id': other_id})['statuses'][0]
        other_ticket = execute(self.outsider, 'create_ticket', {'project_id': other_id, 'title': 'Privat'})
        other_tag = execute(self.outsider, 'create_tag', {'project_id': other_id, 'name': 'Privat'})
        for fields in [{'status_id': other_status['id']}, {'parent_id': other_ticket['id']}, {'tag_ids': [other_tag['id']]}, {'assignee_ids': [self.outsider.pk]}]:
            with self.assertRaises(WorkError):
                self.action('create_ticket', title='Falsch', **fields)
        self.assertFalse(Ticket.objects.filter(project_id=self.project['id']).exists())
        self.assertEqual(Project.objects.get(pk=self.project['id']).next_number, 1)

    def test_duplicate_names_and_keys(self):
        self.action('create_tag', name='Frontend')
        with self.assertRaises(WorkError): self.action('create_tag', name='frontend')
        with self.assertRaises(WorkError): self.action('create_status', name='offen', category='open')
        with self.assertRaises(WorkError): execute(self.owner, 'create_project', {'name': 'Noch eins', 'key': 'web'})

    def test_membership_management_and_revocation(self):
        ticket = self.action('create_ticket', title='Zugewiesen', assignee_ids=[self.member.pk])
        with self.assertRaises(WorkError): self.action('remove_project_member', user=self.member, user_id=self.owner.pk)
        with self.assertRaises(WorkError): self.action('remove_project_member', user_id=self.owner.pk)
        self.action('remove_project_member', user_id=self.member.pk)
        self.assertFalse(Ticket.objects.get(pk=ticket['id']).assignees.exists())
        with self.assertRaises(WorkError): self.action('get_project', user=self.member)
        self.assertEqual(execute(self.member, 'list_projects', {})['projects'], [])

    def test_inactive_members_not_assignable(self):
        self.member.is_active = False
        self.member.save()
        try:
            self.assertNotIn(self.member.pk, [m['id'] for m in self.action('get_project')['members']])
            with self.assertRaises(WorkError): self.action('create_ticket', title='Nicht möglich', assignee_ids=[self.member.pk])
            with self.assertRaises(WorkError): self.action('get_project', user=self.member)
        finally:
            self.member.is_active = True
            self.member.save()

    def test_search_filters_and_pagination(self):
        tag = self.action('create_tag', name='Bug')
        self.action('create_ticket', title='Fehler beheben', tag_ids=[tag['id']], assignee_ids=[self.member.pk])
        self.action('create_ticket', title='Design')
        result = self.action('list_tickets', query='Fehler', tag_id=tag['id'], assignee_id=self.member.pk)
        self.assertEqual(result['total'], 1)
        result = self.action('list_tickets', limit=1, offset=1)
        self.assertEqual(result['total'], 2)
        self.assertEqual(len(result['tickets']), 1)

    def test_optimistic_update_detects_conflict(self):
        ticket = self.action('create_ticket', title='Erste Version')
        self.action('update_ticket', ticket_id=ticket['id'], title='MCP hat geändert')
        with self.assertRaises(WorkError) as cm:
            self.action('update_ticket', ticket_id=ticket['id'], title='Altes Formular', expected_updated_at=ticket['updated_at'])
        self.assertEqual(cm.exception.status, 409)
        self.assertEqual(Ticket.objects.get(pk=ticket['id']).title, 'MCP hat geändert')

    def test_strict_input_and_invalid_date_roll_back(self):
        for fields in [{'title': ' '}, {'title': 'Test', 'due_date': '2026-02-30'}, {'title': 'Test', 'assignee_ids': [self.owner.pk, self.owner.pk]}, {'title': 'Test', 'status_id': True}, {'title': 'Test', 'priority': 'unknown'}, {'title': 'Test', 'unexpected': 1}]:
            with self.assertRaises(WorkError): self.action('create_ticket', **fields)
        self.assertEqual(Ticket.objects.filter(project_id=self.project['id']).count(), 0)

    def test_api_requires_session_and_csrf_and_scopes_projects(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/work/projects/').status_code, 401)
        client.force_login(self.owner)
        body = json.dumps({'action': 'create_ticket', 'arguments': {'project_id': self.project['id'], 'title': 'API Ticket'}})
        self.assertEqual(client.post('/api/work/actions/', body, content_type='application/json').status_code, 403)
        token = client.get('/api/auth/session/').json()['csrfToken']
        result = client.post('/api/work/actions/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['result']['title'], 'API Ticket')
        self.assertIn('no-store', client.get('/api/work/projects/').headers['Cache-Control'])
        self.assertEqual(client.get(f"/api/work/projects/{self.other['id']}/").status_code, 404)
        malformed = client.post('/api/work/actions/', '[]', content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(malformed.status_code, 400)


class McpTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('mcp@example.test')
        self.project = execute(self.user, 'create_project', {'name': 'MCP', 'key': 'MCP'})

    def test_sdk_discovery_dynamic_status_and_errors(self):
        from mcp_server import create_server

        async def exercise():
            async with McpClient(create_server(self.user.email)) as client:
                tools = await client.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, set(OPERATIONS))
                status = await client.call_tool('create_status', {'project_id': self.project['id'], 'name': 'Review per MCP', 'category': 'in_progress'})
                self.assertFalse(status.is_error)
                status_id = status.structured_content['id']
                ticket = await client.call_tool('create_ticket', {'project_id': self.project['id'], 'title': 'MCP Ticket', 'status_id': status_id})
                self.assertFalse(ticket.is_error)
                snapshot = await client.call_tool('get_project', {'project_id': self.project['id']})
                self.assertIn('Review per MCP', [s['name'] for s in snapshot.structured_content['statuses']])
                self.assertEqual(snapshot.structured_content['tickets'][0]['status_id'], status_id)
                denied = await client.call_tool('get_project', {'project_id': self.project['id'] + 999})
                self.assertTrue(denied.is_error)
                invalid = await client.call_tool('create_ticket', {'project_id': self.project['id'], 'title': 'Falsch', 'status_id': 999999})
                self.assertTrue(invalid.is_error)
        async_to_sync(exercise)()
        self.assertEqual(self.project['id'], Ticket.objects.get(title='MCP Ticket').project_id)

    def test_workspace_creation_sharing_and_jira_import_through_sdk(self):
        from mcp_server import create_server
        from unittest.mock import patch
        from .test_workspaces_jira import remote_issue
        from .models import JiraConnection

        async def exercise():
            async with McpClient(create_server(self.user.email)) as client:
                space = await client.call_tool('create_workspace', {'name': 'MCP Workspace'})
                self.assertFalse(space.is_error)
                space_id = space.structured_content['id']
                config = await client.call_tool('configure_jira', {'workspace_id': space_id, 'base_url': 'https://example.atlassian.net', 'email': self.user.email, 'api_token': 'fixture-mcp-secret'})
                self.assertFalse(config.is_error)
                preview = await client.call_tool('preview_jira', {'workspace_id': space_id, 'jql': 'project=WEB'})
                self.assertFalse(preview.is_error)
                imported = await client.call_tool('import_jira', {'workspace_id': space_id, 'issue_keys': ['WEB-1']})
                self.assertFalse(imported.is_error)
                self.assertEqual(imported.structured_content['created'], ['WEB-1'])
                projects = await client.call_tool('list_projects', {'workspace_id': space_id})
                self.assertEqual(len(projects.structured_content['projects']), 1)
                self.assertNotIn('fixture-mcp-secret', str(config))
                annotations = {t.name: t.annotations for t in (await client.list_tools()).tools}
                self.assertTrue(annotations['preview_jira'].open_world_hint)
                self.assertTrue(annotations['preview_jira'].read_only_hint)
        def remote(*args, **kwargs):
            return {'accountId': 'me'} if args[3] == 'myself' else {'issues': [remote_issue(assignee=None)]}
        with patch('modules.work.jira.jira_request', side_effect=remote):
            async_to_sync(exercise)()
        self.assertEqual(JiraConnection.objects.count(), 1)

    def test_mcp_rechecks_account_state(self):
        from mcp_server import create_server
        from asgiref.sync import sync_to_async
        async def exercise():
            async with McpClient(create_server(self.user.email)) as client:
                self.assertFalse((await client.call_tool('list_projects', {})).is_error)
                await sync_to_async(get_user_model().objects.filter(pk=self.user.pk).update)(is_active=False)
                self.assertTrue((await client.call_tool('list_projects', {})).is_error)
        async_to_sync(exercise)()

    def test_stdio_transport_with_real_subprocess(self):
        config = connection.settings_dict
        url = f"postgresql://{quote(config['USER'], safe='')}:{quote(config['PASSWORD'], safe='')}@{config['HOST'] or 'localhost'}:{config['PORT'] or 5432}/{quote(config['NAME'], safe='')}"
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).resolve().parents[2] / 'mcp_server.py'), '--user', self.user.email],
            env={**os.environ, 'DATABASE_URL': url},
        )
        async def exercise():
            async with McpClient(params) as client:
                self.assertEqual(len((await client.list_tools()).tools), len(OPERATIONS))
                result = await client.call_tool('create_ticket', {'project_id': self.project['id'], 'title': 'Echter stdio-Aufruf'})
                self.assertFalse(result.is_error)
        async_to_sync(exercise)()
        self.assertTrue(Ticket.objects.filter(title='Echter stdio-Aufruf').exists())

    def test_parallel_ticket_numbers_are_unique(self):
        from concurrent.futures import ThreadPoolExecutor
        def create(index):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                return execute(user, 'create_ticket', {'project_id': self.project['id'], 'title': f'Parallel {index}'})['key']
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            keys = list(pool.map(create, [1, 2]))
        self.assertEqual(set(keys), {'MCP-1', 'MCP-2'})
