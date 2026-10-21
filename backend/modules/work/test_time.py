import csv
from datetime import timedelta
from io import StringIO
import json

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone
from mcp import Client as McpClient

from .models import TimeEntry
from .services import WorkError, execute


class TimeTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('time-owner@example.test')
        cls.member = User.objects.create_user('time-member@example.test', first_name='Mia')
        cls.outsider = User.objects.create_user('time-outside@example.test', is_staff=True)
        cls.project = execute(cls.owner, 'create_project', {'name': 'Team', 'key': 'TEAM'})
        cls.second = execute(cls.owner, 'create_project', {'name': 'Zweitprojekt', 'key': 'SECOND'})
        cls.private = execute(cls.outsider, 'create_project', {'name': 'Privat', 'key': 'PRIV'})
        execute(cls.owner, 'add_project_member', {'project_id': cls.project['id'], 'email': cls.member.email})
        cls.ticket = execute(cls.owner, 'create_ticket', {'project_id': cls.project['id'], 'title': 'Arbeit'})
        cls.second_ticket = execute(cls.owner, 'create_ticket', {'project_id': cls.second['id'], 'title': 'Weitere Arbeit'})
        cls.private_ticket = execute(cls.outsider, 'create_ticket', {'project_id': cls.private['id'], 'title': 'Privat'})

    def action(self, operation, actor=None, **args):
        return execute(actor or self.owner, operation, {'project_id': self.project['id'], **args})

    def book(self, minutes=30, actor=None, **extra):
        return self.action('create_time_entry', actor=actor, ticket_id=self.ticket['id'], work_date=timezone.localdate().isoformat(), minutes=minutes, **extra)

    def test_booking_is_owned_by_actor_and_ticket_totals_update(self):
        entry = self.book(90, actor=self.member, note='Entwicklung')
        self.assertEqual(entry['user']['id'], self.member.pk)
        self.assertTrue(entry['can_edit'])
        self.assertEqual(entry['ticket_key'], 'TEAM-1')
        self.book(15)
        ticket = self.action('get_ticket', ticket_id=self.ticket['id'])
        self.assertEqual(ticket['logged_minutes'], 105)
        self.assertEqual(self.action('get_project')['tickets'][0]['logged_minutes'], 105)
        self.assertEqual(self.action('list_tickets')['tickets'][0]['logged_minutes'], 105)

    def test_only_own_entries_can_be_changed_including_by_owner(self):
        entry = self.book(actor=self.member)
        for operation in ['update_time_entry', 'delete_time_entry']:
            with self.assertRaises(WorkError) as error:
                self.action(operation, entry_id=entry['id'], **({'minutes': 45} if operation.startswith('update') else {}))
            self.assertEqual(error.exception.status, 403)
        changed = self.action('update_time_entry', actor=self.member, entry_id=entry['id'], minutes=45, note='Korrektur', expected_updated_at=entry['updated_at'])
        self.assertEqual(changed['minutes'], 45)
        with self.assertRaises(WorkError) as error:
            self.action('update_time_entry', actor=self.member, entry_id=entry['id'], minutes=50, expected_updated_at=entry['updated_at'])
        self.assertEqual(error.exception.status, 409)
        self.action('delete_time_entry', actor=self.member, entry_id=entry['id'], expected_updated_at=changed['updated_at'])
        self.assertFalse(TimeEntry.objects.exists())

    def test_no_impersonation_or_cross_project_booking(self):
        with self.assertRaises(WorkError):
            self.book(user_id=self.member.pk)
        with self.assertRaises(WorkError):
            self.action('create_time_entry', ticket_id=self.private_ticket['id'], work_date=timezone.localdate().isoformat(), minutes=30)
        for operation in ['create_time_entry', 'list_time_entries', 'get_time_report', 'export_time_report']:
            args = {'ticket_id': self.ticket['id'], 'work_date': timezone.localdate().isoformat(), 'minutes': 30} if operation == 'create_time_entry' else {}
            with self.assertRaises(WorkError) as error:
                self.action(operation, actor=self.outsider, **args)
            self.assertEqual(error.exception.status, 404)

    def test_invalid_minutes_dates_and_notes_are_rejected(self):
        for minutes in [0, -1, 1441, True, 1.5, '30']:
            with self.subTest(minutes=minutes), self.assertRaises(WorkError):
                self.book(minutes=minutes)
        for work_date in ['2026-02-30', '2026-2-3', (timezone.localdate() + timedelta(days=1)).isoformat()]:
            with self.subTest(work_date=work_date), self.assertRaises(WorkError):
                self.action('create_time_entry', ticket_id=self.ticket['id'], work_date=work_date, minutes=30)
        with self.assertRaises(WorkError):
            self.book(note='x' * 2001)
        self.assertEqual(TimeEntry.objects.count(), 0)
        entry = self.book(minutes=1440)
        self.assertEqual(entry['minutes'], 1440)

    def test_database_enforces_duration(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(ticket_id=self.ticket['id'], user=self.owner, work_date=timezone.localdate(), minutes=0)

    def test_team_report_and_cross_project_totals(self):
        self.book(90)
        self.book(45, actor=self.member)
        execute(self.owner, 'create_time_entry', {'project_id': self.second['id'], 'ticket_id': self.second_ticket['id'], 'work_date': timezone.localdate().isoformat(), 'minutes': 60})
        execute(self.outsider, 'create_time_entry', {'project_id': self.private['id'], 'ticket_id': self.private_ticket['id'], 'work_date': timezone.localdate().isoformat(), 'minutes': 500})
        report = execute(self.owner, 'get_time_report', {})
        self.assertEqual(report['total_minutes'], 195)
        self.assertEqual(report['entry_count'], 3)
        self.assertEqual(report['people_count'], 2)
        self.assertEqual(report['ticket_count'], 2)
        self.assertEqual({p['key'] for p in report['projects']}, {'TEAM', 'SECOND'})
        people = {row['id']: row['minutes'] for row in report['users']}
        self.assertEqual(people, {self.owner.pk: 150, self.member.pk: 45})
        self.assertEqual(report['days'][0]['minutes'], 195)
        json.dumps(report)  # MCP results must contain no unserializable dates.
        self.assertEqual(execute(self.member, 'get_time_report', {})['total_minutes'], 135)

    def test_date_and_person_filters_pagination_and_default_period(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self.action('create_time_entry', ticket_id=self.ticket['id'], work_date=yesterday.isoformat(), minutes=20)
        self.book(35, actor=self.member)
        report = self.action('get_time_report', date_from=today.isoformat(), date_to=today.isoformat(), user_id=self.member.pk)
        self.assertEqual(report['total_minutes'], 35)
        self.assertEqual(len(report['users']), 1)
        listed = self.action('list_time_entries', ticket_id=self.ticket['id'], offset=1, limit=1)
        self.assertEqual(listed['total'], 2)
        self.assertEqual(listed['total_minutes'], 55)
        self.assertEqual(len(listed['entries']), 1)
        default = self.action('get_time_report')
        self.assertEqual(default['date_from'], today.replace(day=1).isoformat())
        self.assertEqual(default['date_to'], today.isoformat())
        for operation in ['get_time_report', 'list_time_entries', 'export_time_report']:
            with self.assertRaises(WorkError):
                self.action(operation, date_from=today.isoformat(), date_to=yesterday.isoformat())

    def test_member_removal_preserves_history_but_revokes_access(self):
        self.book(75, actor=self.member)
        self.action('remove_project_member', user_id=self.member.pk)
        report = self.action('get_time_report')
        self.assertEqual(report['total_minutes'], 75)
        self.assertIn(self.member.pk, [p['id'] for p in report['users']])
        with self.assertRaises(WorkError):
            self.action('list_time_entries', actor=self.member)
        self.assertEqual(execute(self.member, 'get_time_report', {})['total_minutes'], 0)

    def test_ticket_with_bookings_is_not_deleted(self):
        self.book()
        with self.assertRaises(WorkError):
            self.action('delete_ticket', ticket_id=self.ticket['id'])
        self.assertEqual(TimeEntry.objects.count(), 1)

    def test_csv_uses_same_filters_and_escapes_spreadsheet_formulas(self):
        self.book(90, note='=HYPERLINK("https://example.test")')
        self.book(45, actor=self.member, note='Notiz; mit\nZeilenumbruch')
        exported = self.action('export_time_report', user_id=self.owner.pk)
        rows = list(csv.reader(StringIO(exported['csv'].lstrip('\ufeff')), delimiter=';'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][6], '90')
        self.assertTrue(rows[1][7].startswith("'="))
        self.assertTrue(exported['filename'].endswith('.csv'))

    def test_http_auth_csrf_export_and_validation(self):
        client = Client(enforce_csrf_checks=True)
        for path in ['/api/work/time/entries/', '/api/work/time/report/', '/api/work/time/export/']:
            self.assertEqual(client.get(path).status_code, 401)
        client.force_login(self.owner)
        args = {'action': 'create_time_entry', 'arguments': {'project_id': self.project['id'], 'ticket_id': self.ticket['id'], 'work_date': timezone.localdate().isoformat(), 'minutes': 65}}
        body = json.dumps(args)
        self.assertEqual(client.post('/api/work/actions/', body, content_type='application/json').status_code, 403)
        token = client.get('/api/auth/session/').json()['csrfToken']
        self.assertEqual(client.post('/api/work/actions/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)
        response = client.get('/api/work/time/report/', {'project_id': self.project['id']})
        self.assertEqual(response.json()['total_minutes'], 65)
        self.assertIn('no-store', response.headers['Cache-Control'])
        exported = client.get('/api/work/time/export/', {'project_id': self.project['id']})
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(exported.headers['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment;', exported.headers['Content-Disposition'])
        self.assertEqual(client.get('/api/work/time/report/', {'project_id': self.private['id']}).status_code, 404)
        self.assertEqual(client.get('/api/work/time/report/', {'project_id': 'invalid'}).status_code, 400)
        self.assertEqual(client.get('/api/work/time/report/', {'unknown': 'x'}).status_code, 400)


class TimeMcpTests(TransactionTestCase):
    def test_mcp_booking_and_report_round_trip(self):
        from mcp_server import create_server
        user = get_user_model().objects.create_user('time-mcp@example.test')
        project = execute(user, 'create_project', {'name': 'Zeiten', 'key': 'TIME'})
        ticket = execute(user, 'create_ticket', {'project_id': project['id'], 'title': 'Arbeit'})
        async def exercise():
            async with McpClient(create_server(user.email)) as client:
                booking = await client.call_tool('create_time_entry', {'project_id': project['id'], 'ticket_id': ticket['id'], 'work_date': timezone.localdate().isoformat(), 'minutes': 80, 'note': 'Per MCP'})
                self.assertFalse(booking.is_error)
                report = await client.call_tool('get_time_report', {})
                self.assertFalse(report.is_error)
                self.assertEqual(report.structured_content['total_minutes'], 80)
                self.assertEqual(report.structured_content['users'][0]['id'], user.pk)
                changed = await client.call_tool('update_time_entry', {'project_id': project['id'], 'entry_id': booking.structured_content['id'], 'minutes': 95})
                self.assertFalse(changed.is_error)
                exported = await client.call_tool('export_time_report', {})
                self.assertFalse(exported.is_error)
                self.assertIn('95', exported.structured_content['csv'])
        async_to_sync(exercise)()
