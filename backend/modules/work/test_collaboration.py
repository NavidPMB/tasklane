import base64
from datetime import timedelta
import hashlib
import json
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .attachments import attachment_path
from .models import Activity, Attachment, Comment, Ticket
from .services import WorkError, execute
from .token_auth import authenticate_token, create_token, execute_with_token, revoke_token


class CollaborationTests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.override = override_settings(PRIVATE_FILE_ROOT=self.directory.name); self.override.enable(); self.addCleanup(self.override.disable)
        U = get_user_model()
        self.owner=U.objects.create_user('collab-owner@example.test')
        self.member=U.objects.create_user('collab-member@example.test')
        self.other=U.objects.create_user('collab-other@example.test',is_staff=True)
        self.project=execute(self.owner,'create_project',{'name':'Collaboration','key':'COL'})
        execute(self.owner,'add_project_member',{'project_id':self.project['id'],'email':self.member.email})
        self.ticket=self.call('create_ticket',title='Ticket')
        self.outside=execute(self.other,'create_project',{'name':'Outside','key':'OUT'})
        self.other_ticket=execute(self.other,'create_ticket',{'project_id':self.outside['id'],'title':'Outside'})

    def call(self, action, user=None, **args):
        return execute(user or self.owner,action,{'project_id':self.project['id'],**args})

    def file(self, user=None, data=b'private content', **extra):
        upload=self.call('start_attachment_upload',user=user,ticket_id=self.ticket['id'],filename='bericht.txt',size=len(data),sha256=hashlib.sha256(data).hexdigest(),**extra)
        if data:self.call('put_attachment_chunk',user=user,attachment_id=upload['id'],offset=0,data_base64=base64.b64encode(data).decode())
        return self.call('complete_attachment_upload',user=user,attachment_id=upload['id'])

    def test_comments_author_conflict_soft_delete_and_project_scope(self):
        comment=self.call('create_comment',user=self.member,ticket_id=self.ticket['id'],body='**Markdown**')
        with self.assertRaises(WorkError):self.call('update_comment',ticket_id=self.ticket['id'],comment_id=comment['id'],body='Other')
        changed=self.call('update_comment',user=self.member,ticket_id=self.ticket['id'],comment_id=comment['id'],body='Changed',expected_updated_at=comment['updated_at'])
        with self.assertRaises(WorkError) as error:self.call('update_comment',user=self.member,ticket_id=self.ticket['id'],comment_id=comment['id'],body='Stale',expected_updated_at=comment['updated_at'])
        self.assertEqual(error.exception.status,409)
        self.call('delete_comment',user=self.member,ticket_id=self.ticket['id'],comment_id=comment['id'],expected_updated_at=changed['updated_at'])
        self.assertEqual(self.call('list_comments',ticket_id=self.ticket['id'])['comments'][0]['body'],'')
        self.assertTrue(Comment.objects.get(pk=comment['id']).deleted_at)
        for action in ['list_comments','list_checklists','list_attachments']:
            with self.assertRaises(WorkError):self.call(action,ticket_id=self.other_ticket['id'])
            with self.assertRaises(WorkError):self.call(action,user=self.other,ticket_id=self.ticket['id'])

    def test_checklists_assignment_reorder_conflicts_and_counts(self):
        checklist=self.call('create_checklist',ticket_id=self.ticket['id'],name='Abnahme')
        args={'ticket_id':self.ticket['id'],'checklist_id':checklist['id']}
        a=self.call('create_checklist_item',title='First',**args)
        b=self.call('create_checklist_item',title='Second',assignee_id=self.member.pk,**args)
        self.call('update_checklist_item',item_id=b['id'],done=True,position=0,expected_updated_at=b['updated_at'],**args)
        items=self.call('list_checklists',ticket_id=self.ticket['id'])['checklists'][0]['items']
        self.assertEqual([i['id'] for i in items],[b['id'],a['id']])
        snapshot=self.call('get_ticket',ticket_id=self.ticket['id'])
        self.assertEqual((snapshot['checklist_total'],snapshot['checklist_done']),(2,1))
        with self.assertRaises(WorkError):self.call('create_checklist_item',title='Invalid',assignee_id=self.other.pk,**args)
        with self.assertRaises(WorkError):self.call('update_checklist_item',item_id=b['id'],title='Stale',expected_updated_at=b['updated_at'],**args)
        self.call('delete_checklist_item',item_id=a['id'],**args)
        self.assertTrue(self.call('list_activity',ticket_id=self.ticket['id'])['total']>=4)

    def test_typed_fields_required_boolean_and_option_preservation(self):
        self.call('create_custom_field',key='reference',name='Referenz',kind='text',required=True)
        self.call('create_custom_field',key='approved',name='Freigegeben',kind='boolean')
        select=self.call('create_custom_field',key='size',name='Größe',kind='select',options=['S','L'])
        with self.assertRaises(WorkError):self.call('create_ticket',title='Missing')
        t=self.call('create_ticket',title='Full',custom_fields={'reference':'X-1','approved':False,'size':'L'})
        self.assertEqual(t['custom_fields']['approved'],False)
        with self.assertRaises(WorkError):self.call('update_custom_field',field_id=select['id'],options=['S'])
        with self.assertRaises(WorkError):self.call('update_ticket',ticket_id=t['id'],custom_fields={'size':'Unknown'})
        with self.assertRaises(WorkError):self.call('update_ticket',ticket_id=t['id'],custom_fields={'approved':1})
        self.call('update_custom_field',field_id=select['id'],archived=True)
        self.call('update_ticket',ticket_id=t['id'],title='Still editable')
        self.assertEqual(self.call('get_ticket',ticket_id=t['id'])['custom_fields']['size'],'L')
        with self.assertRaises(WorkError):self.call('create_custom_field',user=self.member,key='no',name='No',kind='text')

    def test_project_fields_and_other_types_validate(self):
        field=self.call('create_custom_field',key='budget',name='Budget',kind='number',scope='project',project_value=120.5)
        self.assertEqual(field['project_value'],120.5)
        self.call('create_custom_field',key='date',name='Termin',kind='date')
        self.call('create_custom_field',key='url',name='Link',kind='url')
        self.call('create_custom_field',key='options',name='Optionen',kind='multiselect',options=['A','B'])
        for values in [{'date':'2026-02-30'},{'url':'javascript:alert(1)'},{'options':['A','A']},{'unknown':'x'}]:
            with self.assertRaises(WorkError):self.call('update_ticket',ticket_id=self.ticket['id'],custom_fields=values)
        self.call('update_ticket',ticket_id=self.ticket['id'],custom_fields={'date':'2026-10-26','url':'https://example.test','options':['A','B']})
        self.assertEqual(len(self.call('get_project')['custom_fields']),4)

    def test_private_upload_download_integrity_permissions_and_comment(self):
        comment=self.call('create_comment',ticket_id=self.ticket['id'],body='Attachment')
        file=self.file(comment_id=comment['id'])
        self.assertEqual(file['sha256'],hashlib.sha256(b'private content').hexdigest())
        part=self.call('read_attachment_chunk',user=self.member,attachment_id=file['id'],max_bytes=5)
        self.assertEqual(base64.b64decode(part['data_base64']),b'priva');self.assertFalse(part['eof'])
        for action in ['read_attachment_chunk','delete_attachment']:
            with self.assertRaises(WorkError):self.call(action,user=self.other,attachment_id=file['id'])
        client=Client();url=file['download_url']
        self.assertEqual(client.get(url).status_code,401)
        client.force_login(self.member);response=client.get(url)
        self.assertEqual(response.status_code,200);self.assertIn('attachment;',response['Content-Disposition'])
        self.assertIn('no-store',response['Cache-Control']);self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertEqual(b''.join(response.streaming_content),b'private content');response.close()
        client.force_login(self.other);self.assertEqual(client.get(url).status_code,404)
        listed=self.call('list_attachments',ticket_id=self.ticket['id'],comment_id=comment['id'])
        self.assertEqual(len(listed['attachments']),1)
        self.call('delete_comment',ticket_id=self.ticket['id'],comment_id=comment['id'])
        self.assertEqual(len(self.call('list_attachments',ticket_id=self.ticket['id'])['attachments']),1)

    def test_upload_retry_offsets_hash_and_limits(self):
        upload=self.call('start_attachment_upload',ticket_id=self.ticket['id'],filename='../../safe.txt',size=3,sha256='0'*64)
        self.assertEqual(upload['filename'],'safe.txt')
        with self.assertRaises(WorkError):self.call('complete_attachment_upload',attachment_id=upload['id'])
        with self.assertRaises(WorkError):self.call('put_attachment_chunk',user=self.member,attachment_id=upload['id'],offset=0,data_base64='YWJj')
        self.call('put_attachment_chunk',attachment_id=upload['id'],offset=0,data_base64='YWJj')
        with self.assertRaises(WorkError):self.call('put_attachment_chunk',attachment_id=upload['id'],offset=0,data_base64='YWJj')
        with self.assertRaises(WorkError):self.call('complete_attachment_upload',attachment_id=upload['id'])
        self.call('cancel_attachment_upload',attachment_id=upload['id'])
        self.assertFalse(attachment_path(Attachment.objects.get(pk=upload['id'])).exists())
        with override_settings(ATTACHMENT_MAX_BYTES=2):
            with self.assertRaises(WorkError):self.file(data=b'123')
        empty=self.file(data=b'');self.assertTrue(self.call('read_attachment_chunk',attachment_id=empty['id'])['eof'])

    def test_multipart_requires_csrf_and_download_is_private(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        url=f"/api/work/projects/{self.project['id']}/tickets/{self.ticket['id']}/attachments/"
        self.assertEqual(client.post(url,{'file':SimpleUploadedFile('test.txt',b'contents')}).status_code,403)
        csrf=client.get('/api/auth/session/').json()['csrfToken']
        response=client.post(url,{'file':SimpleUploadedFile('test.txt',b'contents',content_type='text/plain')},HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['result']['size'],8)
        self.assertEqual(self.call('get_project')['tickets'][0]['attachment_count'],1)

    def test_file_delete_roles_and_disk_cleanup(self):
        f=self.file(user=self.member)
        self.call('delete_attachment',attachment_id=f['id'])
        self.assertFalse(attachment_path(Attachment.objects.get(pk=f['id'])).exists())
        self.assertEqual(self.call('list_attachments',ticket_id=self.ticket['id'])['attachments'],[])
        self.assertEqual(self.call('get_ticket',ticket_id=self.ticket['id'])['attachment_count'],0)

    def test_snapshot_aggregates_do_not_multiply_logged_time(self):
        self.call('create_time_entry',ticket_id=self.ticket['id'],work_date=timezone.localdate().isoformat(),minutes=30)
        self.call('create_time_entry',ticket_id=self.ticket['id'],work_date=timezone.localdate().isoformat(),minutes=60)
        for i in range(3):self.call('create_comment',ticket_id=self.ticket['id'],body=str(i))
        self.file()
        snapshot=self.call('get_project')['tickets'][0]
        self.assertEqual(snapshot['logged_minutes'],90)
        self.assertEqual(snapshot['comment_count'],3);self.assertEqual(snapshot['attachment_count'],1)
        self.assertIn('ticket=',snapshot['web_url'])

    def test_cleanup_only_removes_expired_pending_files_after_preview(self):
        ready = self.file()
        pending = self.call('start_attachment_upload', ticket_id=self.ticket['id'], filename='pending.txt', size=5)
        self.call('put_attachment_chunk', attachment_id=pending['id'], offset=0, data_base64='aGk=')
        Attachment.objects.filter(pk=pending['id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(WorkError) as error:
            self.call('get_attachment_upload', attachment_id=pending['id'])
        self.assertEqual(error.exception.status, 410)
        pending_row = Attachment.objects.get(pk=pending['id'])
        call_command('cleanup_uploads', stdout=StringIO())
        self.assertTrue(attachment_path(pending_row).exists())
        call_command('cleanup_uploads', apply=True, stdout=StringIO())
        self.assertFalse(attachment_path(pending_row).exists())
        self.assertEqual(Attachment.objects.get(pk=pending['id']).state, 'deleted')
        self.assertEqual(self.call('read_attachment_chunk', attachment_id=ready['id'])['state'], 'ready')


class IntegrationAccessTests(TestCase):
    def setUp(self):
        U=get_user_model();self.user=U.objects.create_user('api-owner@example.test');self.other=U.objects.create_user('api-other@example.test')
        self.workspace=execute(self.user,'create_workspace',{'name':'Shared'})
        self.project=execute(self.user,'create_project',{'workspace_id':self.workspace['id'],'name':'API','key':'API'})
        self.private=execute(self.user,'create_project',{'name':'Private','key':'PRV'})

    def grant(self,scope='read',workspace=True):
        result=create_token(self.user,'Integration',scope=scope,workspace_id=self.workspace['id'] if workspace else None)
        return result,authenticate_token(result['token'])

    def test_audience_expiry_revocation_encryption_and_inactive_account(self):
        info,grant=self.grant()
        self.assertNotIn(info['token'],grant.credential.encrypted_secret)
        self.assertEqual(grant.credential.get_secret(),info['token'])
        with override_settings(PUBLIC_URL='https://other.example.test'):
            with self.assertRaises(WorkError):authenticate_token(info['token'])
        grant.expires_at=timezone.now()-timedelta(seconds=1);grant.save(update_fields=['expires_at'])
        with self.assertRaises(WorkError):authenticate_token(info['token'])
        info,grant=self.grant();revoke_token(self.user,grant.pk)
        with self.assertRaises(WorkError):authenticate_token(info['token'])
        info,grant=self.grant();self.user.is_active=False;self.user.save()
        with self.assertRaises(WorkError):authenticate_token(info['token'])

    def test_scopes_and_workspace_boundaries(self):
        info,read=self.grant()
        with self.assertRaises(WorkError):execute_with_token(read,'create_ticket',{'project_id':self.project['id'],'title':'No'})
        self.assertEqual([p['id'] for p in execute_with_token(read,'list_projects',{})['projects']],[self.project['id']])
        with self.assertRaises(WorkError):execute_with_token(read,'get_project',{'project_id':self.private['id']})
        self.assertEqual(len(execute_with_token(read,'list_workspaces',{})['workspaces']),1)
        _,write=self.grant('write')
        ticket=execute_with_token(write,'create_ticket',{'project_id':self.project['id'],'title':'Yes'})
        self.assertEqual(ticket['title'],'Yes')
        with self.assertRaises(WorkError):execute_with_token(write,'add_workspace_member',{'workspace_id':self.workspace['id'],'email':self.other.email})
        _,admin=self.grant('manage')
        execute_with_token(admin,'add_workspace_member',{'workspace_id':self.workspace['id'],'email':self.other.email})
        with self.assertRaises(WorkError):execute_with_token(admin,'create_workspace',{'name':'Escape'})

    def test_http_api_rejects_cookies_identity_and_foreign_origin(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.get('/api/v1/projects').status_code,401)
        info,grant=self.grant('write');headers={'HTTP_AUTHORIZATION':'Bearer '+info['token']}
        response=client.get('/api/v1/projects',**headers);self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(client.get('/api/v1/projects',HTTP_ORIGIN='https://evil.example',**headers).status_code,403)
        endpoint='/api/v1/actions/create_ticket'
        payload={'project_id':self.project['id'],'title':'API','user_id':self.other.pk}
        self.assertEqual(client.post(endpoint,json.dumps(payload),content_type='application/json',**headers).status_code,400)
        payload.pop('user_id')
        result=client.post(endpoint,json.dumps(payload),content_type='application/json',**headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(Ticket.objects.get(pk=result.json()['result']['id']).created_by_id,self.user.pk)
        self.assertEqual(client.get('/api/v1/openapi.json').json()['openapi'],'3.1.0')
        revoke_token(self.user,grant.pk)
        self.assertEqual(client.get('/api/v1/projects',**headers).status_code,401)

    def test_token_issue_is_session_csrf_protected_and_only_shows_secret_once(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        body=json.dumps({'name':'UI key','scope':'read','workspace_id':self.workspace['id']})
        self.assertEqual(client.post('/api/work/access-tokens/',body,content_type='application/json').status_code,403)
        csrf=client.get('/api/auth/session/').json()['csrfToken']
        response=client.post('/api/work/access-tokens/',body,content_type='application/json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,201)
        secret=response.json()['token']
        self.assertNotIn(secret,client.get('/api/work/access-tokens/').content.decode())
        client.force_login(self.other)
        self.assertEqual(client.get('/api/work/access-tokens/').json()['tokens'],[])
