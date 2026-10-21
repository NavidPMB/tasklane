import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone
import requests

from integrations.models import IntegrationCredential
from .jira import cloud_url, jira_request
from .models import Workspace, Project, Ticket, JiraIssue, JiraConnection, JiraProject
from .services import execute, WorkError


def remote_issue(key='WEB-1', pk='1001', project_id='200', project_key='WEB', **overrides):
    fields = {'summary': 'Jira ' + key, 'description': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Beschreibung aus Jira'}]}]},
              'project': {'id': project_id, 'key': project_key, 'name': 'Jira ' + project_key},
              'status': {'name': 'Code Review', 'statusCategory': {'key': 'indeterminate'}},
              'labels': ['frontend', 'release'], 'issuetype': {'name': 'Task', 'hierarchyLevel': 0},
              'priority': {'name': 'High'}, 'duedate': '2026-12-01', 'assignee': {'emailAddress': 'sina@example.test'}}
    fields.update(overrides)
    return {'id': pk, 'key': key, 'fields': fields}


class WorkspaceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('owner@example.test')
        self.sina = User.objects.create_user('sina@example.test')
        self.guest = User.objects.create_user('guest@example.test')
        self.other = User.objects.create_user('other@example.test', is_staff=True)
        self.space = execute(self.owner, 'create_workspace', {'name': 'GroupFractal'})
        self.project = execute(self.owner, 'create_project', {'workspace_id': self.space['id'], 'name': 'Website', 'key': 'WEB'})

    def call(self, action, user=None, **args):
        return execute(user or self.owner, action, {'workspace_id': self.space['id'], **args})

    def test_workspace_grants_existing_and_future_project_access_and_assignment(self):
        self.call('add_workspace_member', email=self.sina.email)
        second = self.call('create_project', name='App', key='APP')
        for p in [self.project, second]:
            snap = execute(self.sina, 'get_project', {'project_id': p['id']})
            self.assertIn(self.sina.pk, [u['id'] for u in snap['members']])
            self.assertTrue(next(u['inherited'] for u in snap['members'] if u['id'] == self.sina.pk))
            execute(self.sina, 'create_ticket', {'project_id': p['id'], 'title': 'Shared', 'assignee_ids': [self.sina.pk]})
        self.assertEqual(len(self.call('list_projects', user=self.sina)['projects']), 2)
        own = self.call('create_project', user=self.sina, name='Member project', key='OWN')
        self.assertTrue(execute(self.owner, 'get_project', {'project_id': own['id']})['project']['can_manage'])

    def test_guests_cannot_read_other_projects_or_workspace_team_or_create_projects(self):
        execute(self.owner, 'add_project_member', {'project_id': self.project['id'], 'email': self.guest.email})
        self.call('create_project', name='Secret', key='SEC')
        self.assertEqual(len(self.call('list_projects', user=self.guest)['projects']), 1)
        self.assertEqual(self.call('get_workspace', user=self.guest)['members'], [])
        self.assertFalse(self.call('get_workspace', user=self.guest)['workspace']['can_create_project'])
        for action, args in [('create_project', {'name': 'No', 'key': 'NO'}), ('add_workspace_member', {'email': self.other.email}), ('get_jira_connection', {})]:
            with self.assertRaises(WorkError): self.call(action, user=self.guest, **args)
        with self.assertRaises(WorkError) as error: self.call('get_workspace', user=self.other)
        self.assertEqual(error.exception.status, 404)

    def test_revocation_clears_assignments_but_retains_explicit_project_permissions_and_history(self):
        self.call('add_workspace_member', email=self.sina.email)
        p2 = self.call('create_project', name='Keep', key='KEEP')
        execute(self.owner, 'add_project_member', {'project_id': p2['id'], 'email': self.sina.email})
        t1 = execute(self.sina, 'create_ticket', {'project_id': self.project['id'], 'title': 'Remove', 'assignee_ids': [self.sina.pk]})
        t2 = execute(self.sina, 'create_ticket', {'project_id': p2['id'], 'title': 'Keep', 'assignee_ids': [self.sina.pk]})
        execute(self.sina, 'create_time_entry', {'project_id': self.project['id'], 'ticket_id': t1['id'], 'minutes': 90, 'work_date': timezone.localdate().isoformat()})
        self.call('remove_workspace_member', user_id=self.sina.pk)
        self.assertFalse(Ticket.objects.get(pk=t1['id']).assignees.exists())
        self.assertTrue(Ticket.objects.get(pk=t2['id']).assignees.exists())
        with self.assertRaises(WorkError): execute(self.sina, 'get_project', {'project_id': self.project['id']})
        self.assertEqual(self.call('get_time_report')['total_minutes'], 90)
        self.assertEqual(self.call('get_time_report', user=self.sina)['total_minutes'], 0)

    def test_workspace_filter_and_key_uniqueness(self):
        other = execute(self.owner, 'create_workspace', {'name': 'Other'})
        execute(self.owner, 'create_project', {'workspace_id': other['id'], 'key': 'WEB', 'name': 'Same key'})
        self.assertEqual(len(self.call('list_projects')['projects']), 1)
        with self.assertRaises(WorkError): self.call('create_project', name='Conflict', key='WEB')
        execute(self.owner, 'create_project', {'key': 'PRV', 'name': 'Private default'})
        self.call('add_workspace_member', email=self.sina.email)
        self.assertEqual(len(execute(self.sina, 'list_projects', {})['projects']), 1)
        self.assertEqual(len(execute(self.sina, 'list_workspaces', {})['workspaces']), 1)

    def test_inherited_member_cannot_be_removed_from_one_project(self):
        self.call('add_workspace_member', email=self.sina.email)
        with self.assertRaises(WorkError): execute(self.owner, 'remove_project_member', {'project_id': self.project['id'], 'user_id': self.sina.pk})
        with self.assertRaises(WorkError): self.call('remove_workspace_member', user_id=self.owner.pk)
        with self.assertRaises(WorkError): self.call('add_workspace_member', user=self.sina, email=self.guest.email)


class JiraTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('jira-owner@example.test')
        self.member = User.objects.create_user('sina@example.test')
        self.space = execute(self.owner, 'create_workspace', {'name': 'GroupFractal'})
        execute(self.owner, 'add_workspace_member', {'workspace_id': self.space['id'], 'email': self.member.email})
        with patch('modules.work.jira.jira_request', return_value={'accountId': 'me'}):
            self.configure()

    def configure(self, **args):
        return self.call('configure_jira', base_url='https://example.atlassian.net', email=self.owner.email, api_token='fixture-token-only', **args)

    def call(self, action, user=None, **args):
        return execute(user or self.owner, action, {'workspace_id': self.space['id'], **args})

    def test_credentials_encrypted_and_never_returned_or_shared(self):
        credential = JiraConnection.objects.get(workspace_id=self.space['id']).credential
        self.assertNotIn('fixture-token-only', credential.encrypted_secret)
        self.assertEqual(credential.get_secret(), 'fixture-token-only')
        self.assertNotIn('token', json.dumps(self.call('get_jira_connection')))
        self.assertNotIn('encrypted_secret', json.dumps(self.call('get_jira_connection')))
        for action, args in [('get_jira_connection', {}), ('configure_jira', {'base_url': 'https://example.atlassian.net', 'email': self.owner.email, 'api_token': 'x'}), ('preview_jira', {'jql': 'project=WEB'}), ('import_jira', {'issue_keys': ['WEB-1']})]:
            with patch('modules.work.jira.jira_request') as request:
                with self.assertRaises(WorkError): self.call(action, user=self.member, **args)
                request.assert_not_called()

    def test_bad_auth_does_not_replace_working_token(self):
        with patch('modules.work.jira.jira_request', side_effect=WorkError('Authentication failed')):
            with self.assertRaises(WorkError): self.configure()
        self.assertEqual(JiraConnection.objects.get(workspace_id=self.space['id']).credential.get_secret(), 'fixture-token-only')
        self.assertEqual(IntegrationCredential.objects.filter(key__startswith='jira-').count(), 1)

    def test_only_atlassian_https_allowed(self):
        for url in ['http://example.atlassian.net', 'https://127.0.0.1', 'https://localhost', 'https://jira.example.org', 'https://team.atlassian.net.attacker.test', 'https://team.atlassian.net:8443', 'https://u:p@team.atlassian.net', 'https://team.atlassian.net/path', 'https://team.atlassian.net?url=x', 'https://team.atlassian.net:bad', 'https://[invalid']:
            with self.subTest(url=url), self.assertRaises(WorkError): cloud_url(url)
        self.assertEqual(cloud_url('https://Example.atlassian.net/'), 'https://example.atlassian.net')

    def test_scoped_token_uses_discovered_cloud_gateway_and_preserves_browser_site(self):
        from .jira import JiraAuthenticationError
        cloud_id = '11111111-2222-4333-8444-555555555555'
        with patch('modules.work.jira.jira_request', side_effect=[JiraAuthenticationError('Use gateway'), {'accountId': 'me'}]) as request, patch('modules.work.jira.fetch_jira_json', return_value={'cloudId': cloud_id}) as discover:
            self.configure()
            discover.assert_called_once_with('https://example.atlassian.net/_edge/tenant_info')
            self.assertEqual(request.call_args.kwargs['cloud_id'], cloud_id)
        connection = JiraConnection.objects.get(workspace_id=self.space['id'])
        self.assertEqual(connection.cloud_id, cloud_id)
        self.assertEqual(connection.base_url, 'https://example.atlassian.net')
        with patch('modules.work.jira.fetch_jira_json', return_value={'accountId': 'me'}) as fetch:
            jira_request(connection.base_url, connection.email, 'fixture-secret', 'myself', cloud_id=cloud_id)
            self.assertEqual(fetch.call_args.args[0], 'https://api.atlassian.com/ex/jira/' + cloud_id + '/rest/api/3/myself')

    def test_account_deactivation_during_remote_request_stops_import(self):
        def remote(*args, **kwargs):
            get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
            return {'issues': [remote_issue()]}
        with patch('modules.work.jira.jira_request', side_effect=remote):
            with self.assertRaises(WorkError) as error:
                self.call('import_jira', issue_keys=['WEB-1'])
        self.assertEqual(error.exception.status, 401)
        self.assertFalse(Project.objects.exists())

    def test_connection_rotation_during_remote_request_stops_import(self):
        def remote(*args, **kwargs):
            connection = JiraConnection.objects.get(workspace_id=self.space['id'])
            connection.save()
            return {'issues': [remote_issue()]}
        with patch('modules.work.jira.jira_request', side_effect=remote):
            with self.assertRaises(WorkError) as error:
                self.call('import_jira', issue_keys=['WEB-1'])
        self.assertEqual(error.exception.status, 409)
        self.assertFalse(Project.objects.exists())

    def test_preview_pagination_and_no_side_effects(self):
        with patch('modules.work.jira.jira_request', return_value={'issues': [remote_issue()], 'nextPageToken': 'page2', 'isLast': False}) as request:
            result = self.call('preview_jira', jql='project = WEB', next_page_token='page1')
            self.assertEqual(request.call_args.args[-1]['nextPageToken'], 'page1')
            self.assertEqual(result['next_page_token'], 'page2')
            self.assertFalse(result['issues'][0]['imported'])
        self.assertFalse(Project.objects.exists())

    def test_import_multiple_projects_hierarchy_status_tags_assignees_and_idempotency(self):
        issues = [remote_issue('WEB-2', '1002', parent={'key': 'WEB-1'}), remote_issue(issuetype={'name': 'Epic', 'hierarchyLevel': 1}), remote_issue('APP-1', '2001', '300', 'APP')]
        with patch('modules.work.jira.jira_request', return_value={'issues': issues}):
            result = self.call('import_jira', issue_keys=['WEB-1', 'WEB-2', 'APP-1'])
        self.assertEqual(len(result['projects_created']), 2)
        self.assertEqual(len(result['created']), 3)
        self.assertEqual(result['warnings'], [])
        epic = JiraIssue.objects.get(remote_key='WEB-1').ticket
        child = JiraIssue.objects.get(remote_key='WEB-2').ticket
        self.assertEqual(epic.kind, 'epic')
        self.assertEqual(child.parent_id, epic.pk)
        self.assertEqual(child.status.name, 'Code Review')
        self.assertEqual(child.status.category, 'in_progress')
        self.assertEqual(child.description, 'Beschreibung aus Jira')
        self.assertEqual(list(child.assignees.values_list('id', flat=True)), [self.member.pk])
        self.assertEqual(set(child.tags.values_list('name', flat=True)), {'frontend', 'release'})
        self.assertEqual(child.priority, 'high')
        self.assertEqual(len(execute(self.member, 'list_projects', {})['projects']), 2)
        child.title = 'Local edit'; child.save()
        with patch('modules.work.jira.jira_request', return_value={'issues': issues}):
            repeat = self.call('import_jira', issue_keys=['WEB-1', 'WEB-2', 'APP-1'])
        self.assertEqual(repeat['created'], [])
        self.assertEqual(len(repeat['skipped']), 3)
        child.refresh_from_db(); self.assertEqual(child.title, 'Local edit')
        self.assertEqual(Ticket.objects.count(), 3)
        snapshot = execute(self.member, 'get_project', {'project_id': child.project_id})
        self.assertEqual(next(t['jira']['key'] for t in snapshot['tickets'] if t['id'] == child.pk), 'WEB-2')

    def test_missing_selection_or_invalid_date_rolls_back_every_project(self):
        with patch('modules.work.jira.jira_request', return_value={'issues': [remote_issue()]}):
            with self.assertRaises(WorkError): self.call('import_jira', issue_keys=['WEB-1', 'WEB-2'])
        issues = [remote_issue(), remote_issue('APP-1', '2001', '300', 'APP', duedate='2026-02-30')]
        with patch('modules.work.jira.jira_request', return_value={'issues': issues}):
            with self.assertRaises(WorkError): self.call('import_jira', issue_keys=['WEB-1', 'APP-1'])
        self.assertFalse(Project.objects.exists())
        self.assertFalse(JiraProject.objects.exists())
        self.assertFalse(JiraIssue.objects.exists())

    def test_unknown_assignee_and_missing_parent_return_warnings(self):
        issue = remote_issue(assignee={'displayName': 'Unknown'}, parent={'key': 'WEB-99'})
        with patch('modules.work.jira.jira_request', return_value={'issues': [issue]}):
            result = self.call('import_jira', issue_keys=['WEB-1'])
        self.assertEqual(len(result['warnings']), 2)
        self.assertFalse(Ticket.objects.get().assignees.exists())
        self.assertIsNone(Ticket.objects.get().parent_id)

    def test_project_collision_gets_separate_key_and_connection_cannot_switch_site(self):
        execute(self.owner, 'create_project', {'workspace_id': self.space['id'], 'name': 'Existing local', 'key': 'WEB'})
        with patch('modules.work.jira.jira_request', return_value={'issues': [remote_issue()]}):
            result = self.call('import_jira', issue_keys=['WEB-1'])
        self.assertEqual(result['projects_created'][0]['key'], 'WEB2')
        self.assertEqual(Project.objects.get(key='WEB').tickets.count(), 0)
        with patch('modules.work.jira.jira_request', return_value={'accountId': 'me'}):
            with self.assertRaises(WorkError): self.call('configure_jira', base_url='https://other.atlassian.net', email=self.owner.email, api_token='rotated-fixture')

    def test_strict_selection_schema_and_safe_secret_errors(self):
        for keys in [[], ['WEB-1', 'WEB-1'], ['WEB-1) OR 1=1'], ['WEB-1'] * 51]:
            with patch('modules.work.jira.jira_request') as request:
                with self.assertRaises(WorkError): self.call('import_jira', issue_keys=keys)
                request.assert_not_called()
        secret = 'sensitive' * 300
        with self.assertRaises(WorkError) as error: self.call('configure_jira', base_url='x', email='x', api_token=secret)
        self.assertNotIn(secret, str(error.exception))

    def test_api_auth_csrf_workspace_scope_and_cache_control(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/work/workspaces/').status_code, 401)
        client.force_login(self.owner)
        payload = json.dumps({'action': 'get_jira_connection', 'arguments': {'workspace_id': self.space['id']}})
        self.assertEqual(client.post('/api/work/actions/', payload, content_type='application/json').status_code, 403)
        csrf = client.get('/api/auth/session/').json()['csrfToken']
        response = client.post('/api/work/actions/', payload, content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('fixture-token-only', response.content.decode())
        self.assertIn('no-store', response['Cache-Control'])

    def test_transport_does_not_follow_redirects_and_sanitizes_errors(self):
        response = MagicMock(status_code=302, is_redirect=True)
        session = MagicMock()
        session.__enter__.return_value = session
        session.request.return_value = response
        with patch('modules.work.jira.requests.Session', return_value=session):
            with self.assertRaises(WorkError): jira_request('https://example.atlassian.net', 'user@example.test', 'fixture-secret', 'myself')
        self.assertFalse(session.request.call_args.kwargs['allow_redirects'])
        self.assertFalse(session.trust_env)
        with patch('modules.work.jira.requests.Session', side_effect=requests.Timeout('fixture-secret upstream url')):
            with self.assertRaises(WorkError) as error: jira_request('https://example.atlassian.net', 'user@example.test', 'fixture-secret', 'myself')
        self.assertNotIn('fixture-secret', str(error.exception))


class WorkspaceMigrationTests(TransactionTestCase):
    def test_upgrade_retains_direct_sharing_without_exposing_private_projects(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        before = [('work', '0004_time_guide')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes('work')
        try:
            executor.migrate(before)
            old = executor.loader.project_state(before).apps
            User = old.get_model('accounts', 'User')
            Project = old.get_model('work', 'Project')
            owner = User.objects.create(email='migration-owner@example.test', password='!')
            guest = User.objects.create(email='migration-guest@example.test', password='!')
            shared = Project.objects.create(owner=owner, name='Shared', key='SHR')
            private = Project.objects.create(owner=owner, name='Private', key='PRV')
            shared.members.add(owner, guest); private.members.add(owner)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            from .models import Project as CurrentProject
            owner = get_user_model().objects.get(pk=owner.pk)
            guest = get_user_model().objects.get(pk=guest.pk)
            shared = CurrentProject.objects.get(pk=shared.pk)
            private = CurrentProject.objects.get(pk=private.pk)
            self.assertEqual(shared.workspace_id, private.workspace_id)
            self.assertFalse(shared.workspace.members.filter(pk=guest.pk).exists())
            self.assertEqual([p['key'] for p in execute(guest, 'list_projects', {})['projects']], ['SHR'])
            self.assertEqual(len(execute(owner, 'list_projects', {})['projects']), 2)
        finally:
            MigrationExecutor(connection).migrate(latest)
