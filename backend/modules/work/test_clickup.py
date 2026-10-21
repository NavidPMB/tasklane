from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
import csv
import json
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone
from mcp import Client as McpClient
import requests

from .clickup import clickup_request
from .models import (ClickUpConnection, ClickUpImportBatch, ClickUpPerson, ClickUpProject, ClickUpTask,
                     ClickUpTimeSource, Project, Ticket, TimeEntry)
from .services import WorkError, execute

START = int(datetime(2024, 1, 15, 8, tzinfo=dt_timezone.utc).timestamp()*1000)


def task(task_id='cu1', list_id='100', duration=0, parent=None):
    return {'id': task_id, 'name': 'Abgeschlossene Aufgabe ' + task_id, 'description': 'Historischer Kontext',
            'team_id': '10', 'list': {'id': list_id, 'name': 'Archivprojekt ' + list_id}, 'parent': parent,
            'status': {'status': 'Abgeschlossen', 'type': 'closed'}, 'time_spent': duration,
            'tags': [{'name': 'migration'}], 'priority': {'id': '2'}, 'assignees': [{'id': 2, 'email': 'sina-clickup@example.test'}]}


def entry(entry_id='10001', task_id='cu1', user_id=2, name='Sina', email='sina-clickup@example.test', duration=5400000, start=START):
    return {'id': entry_id, 'task': {'id': task_id}, 'user': {'id': user_id, 'username': name, 'email': email},
            'start': str(start), 'end': str(start+max(0,duration)), 'duration': str(duration), 'description': 'Arbeit aus 2024'}


class ClickUpFixtures:
    def init_remote(self):
        self.remote_tasks = {'cu1': task(duration=5400000)}
        self.remote_entries = {'cu1': [entry()]}
        self.remote_teams = [{'id': '10', 'name': 'Remote Team', 'members': [{'user': {'id': 1}}, {'user': {'id': 2}}, {'user': {'id': 3}}]}]

    def remote(self, token, path, params=None):
        if path == 'user': return {'user': {'id': 1, 'username': 'ClickUp Owner'}}
        if path == 'team': return {'teams': deepcopy(self.remote_teams)}
        if path == 'team/10/space': return {'spaces': [{'id': '20', 'name': 'Abgeschlossene Projekte'}]}
        if path == 'space/20/folder': return {'folders': [{'id': '30', 'name': 'Kunden'}]}
        if path == 'space/20/list': return {'lists': [{'id': '100', 'name': 'Archivprojekt 100'}]}
        if path == 'folder/30/list': return {'lists': [{'id': '200', 'name': 'Archivprojekt 200'}]}
        if path.startswith('list/') and path.endswith('/task'):
            list_id = path.split('/')[1]
            values = [t for t in self.remote_tasks.values() if t['list']['id'] == list_id]
            return {'tasks': deepcopy(values), 'last_page': True}
        if path.startswith('list/'):
            list_id = path.split('/')[1]
            return {'id': list_id, 'name': 'Archivprojekt ' + list_id, 'space': {'id': '20', 'name': 'Archiv'}, 'folder': {'id': '30', 'name': 'Kunden'}}
        if path == 'team/10/time_entries':
            ids = params['assignee'].split(',')
            return {'data': deepcopy([e for e in self.remote_entries.get(params['task_id'], []) if str(e['user']['id']) in ids])}
        if path.startswith('task/') and path.endswith('/time'):
            return {'data': [{'user': e['user']} for e in self.remote_entries.get(path.split('/')[1], [])]}
        if path.startswith('task/'): return deepcopy(self.remote_tasks[path.split('/')[1]])
        raise AssertionError('Unexpected fixture path: ' + path)


class ClickUpTests(ClickUpFixtures, TestCase):
    def setUp(self):
        self.init_remote()
        User = get_user_model()
        self.owner = User.objects.create_user('clickup-owner@example.test')
        self.member = User.objects.create_user('sina-clickup@example.test', first_name='Sina Lokal')
        self.outsider = User.objects.create_user('clickup-staff@example.test', is_staff=True)
        self.workspace = execute(self.owner, 'create_workspace', {'name': 'ClickUp Migration'})
        execute(self.owner, 'add_workspace_member', {'workspace_id': self.workspace['id'], 'email': self.member.email})
        self.mock = patch('modules.work.clickup.clickup_request', side_effect=self.remote).start()
        self.addCleanup(patch.stopall)
        self.call('configure_clickup', api_token='pk_fixture_clickup')

    def call(self, action, user=None, **args):
        return execute(user or self.owner, action, {'workspace_id': self.workspace['id'], **args})

    def prepare(self, ids=None):
        return self.call('prepare_clickup_import', team_id='10', task_ids=ids or ['cu1'])

    def import_plan(self, plan=None):
        plan = plan or self.prepare()
        return self.call('import_clickup', batch_id=plan['batch_id'])

    def test_encrypted_write_only_token_and_owner_only_all_steps(self):
        conn = ClickUpConnection.objects.get()
        self.assertEqual(conn.credential.get_secret(), 'pk_fixture_clickup')
        self.assertNotIn('pk_fixture_clickup', conn.credential.encrypted_secret)
        self.assertNotIn('pk_fixture_clickup', json.dumps(self.call('get_clickup_connection')))
        plan = self.prepare()
        for action, args in [('get_clickup_connection', {}), ('configure_clickup', {'api_token': 'pk_other_fixture'}),
                             ('list_clickup_locations', {}), ('preview_clickup', {'team_id': '10', 'list_id': '100'}),
                             ('prepare_clickup_import', {'team_id': '10', 'task_ids': ['cu1']}), ('import_clickup', {'batch_id': plan['batch_id']})]:
            self.mock.reset_mock()
            for actor in [self.member, self.outsider]:
                with self.subTest(action=action, actor=actor.pk), self.assertRaises(WorkError): self.call(action, user=actor, **args)
            self.mock.assert_not_called()

    def test_failed_rotation_preserves_token_and_redacts_validation(self):
        with patch('modules.work.clickup.clickup_request', side_effect=WorkError('No auth')):
            with self.assertRaises(WorkError): self.call('configure_clickup', api_token='pk_rotated_fixture')
        self.assertEqual(ClickUpConnection.objects.get().credential.get_secret(), 'pk_fixture_clickup')
        secret = 'pk_' + 'private' * 500
        with self.assertRaises(WorkError) as error: self.call('configure_clickup', api_token=secret)
        self.assertNotIn(secret, str(error.exception))

    def test_locations_and_archived_selection(self):
        self.assertEqual(self.call('list_clickup_locations')['teams'][0]['id'], '10')
        self.assertEqual(self.call('list_clickup_locations', team_id='10')['spaces'][0]['id'], '20')
        self.assertEqual(self.call('list_clickup_locations', team_id='10', space_id='20')['folders'][0]['id'], '30')
        self.assertEqual(self.call('list_clickup_locations', team_id='10', space_id='20', folder_id='30', archived=True)['lists'][0]['id'], '200')
        self.assertTrue(any(c.args[2] == {'archived': 'true'} for c in self.mock.call_args_list if len(c.args)>2 and c.args[1]=='folder/30/list'))
        with self.assertRaises(WorkError): self.call('list_clickup_locations', team_id='999')
        with self.assertRaises(WorkError): self.call('list_clickup_locations', space_id='20')

    def test_preview_closed_subtasks_and_pagination(self):
        self.remote_tasks['cu2'] = task('cu2', parent='cu1')
        self.remote_tasks['cu3'] = task('cu3'); self.remote_tasks['cu3']['status']={'status':'Offen', 'type':'open'}
        result = self.call('preview_clickup', team_id='10', list_id='100', only_completed=True)
        self.assertEqual(len(result['tasks']), 2)
        self.assertEqual(result['tasks'][1]['parent_id'], 'cu1')
        request = next(c for c in self.mock.call_args_list if c.args[1]=='list/100/task')
        self.assertEqual(request.args[2]['include_closed'], 'true')
        self.assertEqual(request.args[2]['subtasks'], 'true')
        self.assertFalse(Project.objects.exists())
        with patch('modules.work.clickup.fetch', side_effect=[{'teams':self.remote_teams},{'tasks':[task(str(i+1)) for i in range(100)]}]):
            self.assertEqual(self.call('preview_clickup',team_id='10',list_id='100',page=2)['next_page'],3)

    def test_preflight_loads_all_years_and_checks_source_totals_without_projects(self):
        result = self.prepare()
        self.assertEqual(result['entry_count'], 1)
        self.assertEqual(result['total_minutes'], 90)
        self.assertEqual(result['date_from'], '2024-01-15')
        self.assertEqual(result['people'][0]['name'], 'Sina')
        request = next(c for c in self.mock.call_args_list if c.args[1]=='team/10/time_entries')
        self.assertEqual(request.args[2]['start_date'], 0)
        self.assertIn('2', request.args[2]['assignee'])
        self.assertFalse(Project.objects.exists())
        self.assertEqual(ClickUpImportBatch.objects.count(), 1)

    def test_completed_ticket_hierarchy_projects_tags_and_time_reports(self):
        self.remote_tasks['cu2'] = task('cu2', parent='cu1')
        self.remote_tasks['cu3'] = task('cu3', list_id='200')
        plan = self.prepare(['cu1','cu2','cu3'])
        result = self.import_plan(plan)
        self.assertEqual(len(result['created']),3)
        self.assertEqual(len(result['projects_created']),2)
        self.assertEqual(result['time_entries_created'],1)
        root = ClickUpTask.objects.get(remote_id='cu1').ticket
        child = ClickUpTask.objects.get(remote_id='cu2').ticket
        self.assertEqual(child.parent_id,root.pk)
        self.assertEqual(root.status.category,'closed')
        self.assertEqual(root.priority,'high')
        self.assertEqual(list(root.tags.values_list('name',flat=True)),['migration'])
        self.assertEqual(list(root.assignees.values_list('pk',flat=True)),[self.member.pk])
        report=self.call('get_time_report',date_from='2024-01-01',date_to='2024-12-31')
        self.assertEqual(report['total_minutes'],90)
        self.assertEqual(next(p['minutes'] for p in report['users'] if p['id']==self.member.pk),90)
        snapshot=execute(self.member,'get_project',{'project_id':root.project_id})
        self.assertEqual(next(t['logged_minutes'] for t in snapshot['tickets'] if t['id']==root.pk),90)
        self.assertEqual(next(t['clickup']['url'] for t in snapshot['tickets'] if t['id']==root.pk),'https://app.clickup.com/t/cu1')
        batch=ClickUpImportBatch.objects.get(pk=plan['batch_id']);self.assertEqual(batch.payload,{})
        self.assertTrue(self.import_plan(plan)['replayed'])
        self.assertEqual(TimeEntry.objects.count(),1)

    def test_former_contributors_keep_name_without_account_or_access_and_exact_milliseconds(self):
        self.remote_entries['cu1']=[entry(user_id=3,name='Ehemalige Person',email='former@example.test',duration=30001)]
        self.remote_tasks['cu1']['time_spent']=30001
        account_count=get_user_model().objects.count()
        self.import_plan()
        self.assertEqual(get_user_model().objects.count(),account_count)
        row=TimeEntry.objects.get();self.assertIsNone(row.user_id)
        self.assertEqual(row.duration_ms,30001)
        self.assertEqual(row.external_person.name,'Ehemalige Person')
        report=self.call('get_time_report',date_from='2024-01-01',date_to='2024-12-31')
        self.assertEqual(round(report['total_minutes']*60000),30001)
        historical=next(p for p in report['users'] if p.get('is_external'))
        self.assertLess(historical['id'],0)
        self.assertEqual(historical['name'],'Ehemalige Person')
        filtered=self.call('get_time_report',date_from='2024-01-01',date_to='2024-12-31',user_id=historical['id'])
        self.assertEqual(round(filtered['total_minutes']*60000),30001)
        self.assertEqual(len(filtered['users']),1)
        exported=self.call('export_time_report',date_from='2024-01-01',date_to='2024-12-31',user_id=historical['id'])
        rows=list(csv.reader(StringIO(exported['csv'].lstrip('\ufeff')),delimiter=';'))
        self.assertEqual(rows[1][4],'Ehemalige Person')
        self.assertEqual(rows[1][8],'30001')
        self.assertEqual(rows[1][9],'clickup')
        self.assertEqual(rows[1][11],'Ehemalige Person')
        self.assertEqual(self.call('get_time_report',date_from='2024-01-01',date_to='2024-12-31')['people_count'],1)

    def test_missing_entries_or_running_timers_abort_preflight(self):
        self.remote_entries['cu1']=[]
        with self.assertRaises(WorkError): self.prepare()
        self.assertFalse(ClickUpImportBatch.objects.exists())
        self.remote_entries['cu1']=[entry(duration=-1)]
        with self.assertRaises(WorkError) as error:self.prepare()
        self.assertIn('Timer',str(error.exception))
        self.assertFalse(Project.objects.exists())

    def test_former_workspace_member_is_discovered_and_loaded_via_current_api(self):
        self.remote_entries['cu1'].append(entry('10002',user_id=99,name='Früher',email='former@example.test',duration=120000))
        self.remote_tasks['cu1']['time_spent']+=120000
        plan=self.prepare();self.assertEqual(plan['total_minutes'],92)
        self.assertTrue(any(c.args[1]=='task/cu1/time' for c in self.mock.call_args_list))
        self.assertTrue(any(c.args[1]=='team/10/time_entries' and c.args[2]['assignee']=='99' for c in self.mock.call_args_list))
        self.import_plan(plan);self.assertEqual(ClickUpTimeSource.objects.count(),2)

    def test_duplicate_plans_and_later_missing_time_do_not_overwrite_local_tickets(self):
        first=self.prepare();second=self.prepare();self.import_plan(first)
        ticket=ClickUpTask.objects.get().ticket;ticket.title='Lokale Änderung';ticket.save()
        result=self.import_plan(second)
        self.assertEqual(result['created'],[]);self.assertEqual(result['time_entries_created'],0);self.assertEqual(result['time_entries_skipped'],1)
        self.remote_entries['cu1'].append(entry('10002',duration=60000));self.remote_tasks['cu1']['time_spent']+=60000
        result=self.import_plan()
        self.assertEqual(result['created'],[]);self.assertEqual(result['time_entries_created'],1)
        ticket.refresh_from_db();self.assertEqual(ticket.title,'Lokale Änderung')
        self.assertEqual(TimeEntry.objects.count(),2)

    def test_source_changes_abort_import_and_roll_back_other_tasks(self):
        self.import_plan()
        self.remote_entries['cu1'][0]['description']='Geänderte Quellnotiz'
        self.remote_tasks['cu2']=task('cu2',list_id='200')
        plan=self.prepare(['cu2','cu1'])
        with self.assertRaises(WorkError) as error:self.import_plan(plan)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(Project.objects.count(),1);self.assertEqual(Ticket.objects.count(),1);self.assertEqual(TimeEntry.objects.count(),1)
        self.assertIsNone(ClickUpImportBatch.objects.get(pk=plan['batch_id']).imported_at)

    def test_cycle_rolls_back_tickets_projects_times_and_plan_consumption(self):
        self.remote_tasks['cu1']['parent']='cu2';self.remote_tasks['cu2']=task('cu2',parent='cu1')
        plan=self.prepare(['cu1','cu2'])
        with self.assertRaises(WorkError):self.import_plan(plan)
        self.assertFalse(Project.objects.exists());self.assertFalse(TimeEntry.objects.exists())
        self.assertFalse(ClickUpTimeSource.objects.exists());self.assertFalse(ClickUpPerson.objects.exists())
        self.assertIsNone(ClickUpImportBatch.objects.get(pk=plan['batch_id']).imported_at)

    def test_expired_rotated_wrong_workspace_and_disabled_account_reject_plans(self):
        plan=self.prepare()
        ClickUpImportBatch.objects.filter(pk=plan['batch_id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(WorkError):self.import_plan(plan)
        plan=self.prepare();self.call('configure_clickup',api_token='pk_rotated_fixture')
        with self.assertRaises(WorkError) as error:self.import_plan(plan)
        self.assertEqual(error.exception.status,409)
        other=execute(self.owner,'create_workspace',{'name':'Wrong workspace'})
        with self.assertRaises(WorkError):execute(self.owner,'import_clickup',{'workspace_id':other['id'],'batch_id':plan['batch_id']})
        self.assertFalse(Project.objects.exists())

    def test_precision_timezone_long_entry_and_imported_history_is_immutable(self):
        start=int(datetime(2024,1,15,23,30,tzinfo=dt_timezone.utc).timestamp()*1000)
        duration=86400000+30001
        self.remote_entries['cu1']=[entry(duration=duration,start=start)];self.remote_tasks['cu1']['time_spent']=duration
        self.import_plan()
        self.assertEqual(ClickUpTimeSource.objects.count(),1);self.assertEqual(TimeEntry.objects.count(),2)
        self.assertEqual(set(TimeEntry.objects.values_list('work_date',flat=True)),{datetime(2024,1,16).date()})
        report=self.call('get_time_report',date_from='2024-01-16',date_to='2024-01-16')
        self.assertEqual(round(report['total_minutes']*60000),duration)
        row=TimeEntry.objects.first()
        for action in ('update_time_entry','delete_time_entry'):
            with self.assertRaises(WorkError):execute(self.member,action,{'project_id':row.ticket.project_id,'entry_id':row.pk,**({'minutes':60} if action.startswith('update') else {})})
        listed=self.call('list_time_entries',user=self.member,date_from='2024-01-16',date_to='2024-01-16')
        self.assertFalse(listed['entries'][0]['can_edit']);self.assertEqual(listed['entries'][0]['source']['provider'],'clickup')

    def test_active_account_rechecked_after_network_and_schema_rejects_payload_injection(self):
        def remote(*args,**kwargs):
            result=self.remote(*args,**kwargs)
            if args[1]=='team/10/time_entries':get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
            return result
        with patch('modules.work.clickup.clickup_request',side_effect=remote):
            with self.assertRaises(WorkError) as error:self.prepare()
        self.assertEqual(error.exception.status,401)
        self.assertFalse(ClickUpImportBatch.objects.exists())
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=True)
        for ids in ([],['cu1','cu1'],['../secret'],['cu'+str(i) for i in range(21)]):
            with self.assertRaises(WorkError):self.call('prepare_clickup_import',team_id='10',task_ids=ids)
        with self.assertRaises(WorkError):self.call('import_clickup',batch_id='bad',payload={'tasks':[]})

    def test_database_rejects_ambiguous_persons_and_missing_import_precision(self):
        self.import_plan()
        original=TimeEntry.objects.get()
        source=original.clickup_source
        external=source.person
        invalid=[{'clickup_source':source}, {'user':None}, {'external_person':external},
                 {'clickup_source':source,'duration_ms':0}, {'clickup_source':source,'duration_ms':86400001}, {'duration_ms':30001}]
        for extra in invalid:
            kwargs={'ticket':original.ticket,'user':self.member,'work_date':original.work_date,'minutes':1,**extra}
            with self.subTest(extra=extra), self.assertRaises(IntegrityError), transaction.atomic():TimeEntry.objects.create(**kwargs)

    def test_historical_person_and_exact_csv_do_not_leak_to_staff_outsider(self):
        self.remote_entries['cu1']=[entry(user_id=3,name='Former',email='former@example.test')]
        self.import_plan()
        external_id=-TimeEntry.objects.get().external_person_id
        report=execute(self.outsider,'get_time_report',{'user_id':external_id,'date_from':'2024-01-01','date_to':'2024-12-31'})
        self.assertEqual(report['total_minutes'],0);self.assertEqual(report['users'],[])
        with self.assertRaises(WorkError):self.call('export_time_report',user=self.outsider,user_id=external_id,date_from='2024-01-01',date_to='2024-12-31')

    def test_zero_time_has_notice_and_does_not_create_zero_duration_entries(self):
        self.remote_entries['cu1']=[entry(duration=0)];self.remote_tasks['cu1']['time_spent']=0
        plan=self.prepare();self.assertTrue(plan['warnings']);result=self.import_plan(plan)
        self.assertEqual(result['time_entries_created'],0);self.assertEqual(result['imported_minutes'],0)
        self.assertEqual(Ticket.objects.count(),1);self.assertFalse(TimeEntry.objects.exists())

    def test_http_csrf_and_report_external_person_scope(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        payload=json.dumps({'action':'get_clickup_connection','arguments':{'workspace_id':self.workspace['id']}})
        self.assertEqual(client.post('/api/work/actions/',payload,content_type='application/json').status_code,403)
        csrf=client.get('/api/auth/session/').json()['csrfToken']
        response=client.post('/api/work/actions/',payload,content_type='application/json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,200);self.assertNotIn('pk_fixture_clickup',response.content.decode())
        self.assertIn('no-store',response['Cache-Control'])


class ClickUpTransportTests(TestCase):
    def test_fixed_host_no_redirect_and_safe_errors(self):
        from .clickup import clickup_request
        token='pk_fixture_private'
        session=MagicMock();session.__enter__.return_value=session
        session.get.return_value=MagicMock(status_code=302,is_redirect=True)
        with patch('modules.work.clickup.requests.Session',return_value=session):
            with self.assertRaises(WorkError):clickup_request(token,'user')
        self.assertFalse(session.trust_env)
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertEqual(session.get.call_args.args[0],'https://api.clickup.com/api/v2/user')
        with patch('modules.work.clickup.requests.Session',side_effect=requests.Timeout(token)):
            with self.assertRaises(WorkError) as error:clickup_request(token,'user')
        self.assertNotIn(token,str(error.exception))
        for path in ['https://evil.example','../user','task/a/../../user','team/1/time_entries?url=evil']:
            with self.assertRaises(WorkError):clickup_request(token,path)


class ClickUpMcpTests(ClickUpFixtures, TransactionTestCase):
    def test_full_history_round_trip_with_sdk(self):
        from mcp_server import create_server
        self.init_remote()
        user=get_user_model().objects.create_user('clickup-mcp@example.test')
        async def exercise():
            async with McpClient(create_server(user.email)) as client:
                workspace=(await client.call_tool('create_workspace',{'name':'ClickUp MCP'})).structured_content['id']
                common={'workspace_id':workspace}
                configured=await client.call_tool('configure_clickup',{**common,'api_token':'pk_fixture_mcp'})
                self.assertFalse(configured.is_error)
                locations=await client.call_tool('list_clickup_locations',common);self.assertFalse(locations.is_error)
                plan=await client.call_tool('prepare_clickup_import',{**common,'team_id':'10','task_ids':['cu1']});self.assertFalse(plan.is_error)
                imported=await client.call_tool('import_clickup',{**common,'batch_id':plan.structured_content['batch_id']});self.assertFalse(imported.is_error)
                self.assertEqual(imported.structured_content['time_entries_created'],1)
                report=await client.call_tool('get_time_report',{**common,'date_from':'2024-01-01','date_to':'2024-12-31'})
                self.assertFalse(report.is_error);self.assertEqual(report.structured_content['total_minutes'],90)
                self.assertTrue(next(p for p in report.structured_content['users'] if p['minutes']==90)['is_external'])
        with patch('modules.work.clickup.clickup_request',side_effect=self.remote):async_to_sync(exercise)()
