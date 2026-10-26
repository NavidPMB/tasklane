"""Private Dateien: berechtigungsgeprüfte Downloads und wiederaufnehmbare Uploads."""
import base64
import binascii
from datetime import timedelta
import hashlib
from pathlib import Path
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from .collaboration import event, ticket_for
from .errors import WorkError
from .models import Attachment

UUID_SCHEMA = {'type': 'string', 'pattern': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}
CHUNK_SIZE = 65536


def attachment_path(attachment):
    return Path(settings.PRIVATE_FILE_ROOT) / str(attachment.pk)


def metadata(a):
    return {'id': str(a.pk), 'ticket_id': a.ticket_id, 'comment_id': a.comment_id, 'filename': a.filename,
            'content_type': a.content_type, 'size': a.size, 'received': a.received, 'sha256': a.sha256,
            'state': a.state, 'uploaded_by': a.uploaded_by_id, 'created_at': a.created_at.isoformat(),
            'download_url': f'/api/work/projects/{a.ticket.project_id}/attachments/{a.pk}/content/'}


def attachment_for(user, project_id, attachment_id, *, ready=True, own=False):
    from .services import project_for
    project = project_for(user, project_id)
    a = Attachment.objects.select_related('ticket').filter(pk=attachment_id, ticket__project=project).first()
    if not a or a.state == 'deleted' or (ready and a.state != 'ready'):
        raise WorkError('Anhang nicht gefunden.', 404)
    if own and a.uploaded_by_id != user.pk:
        raise WorkError('Nur eigene Uploads können fortgesetzt oder abgebrochen werden.', 403)
    if a.state == 'uploading' and a.expires_at <= timezone.now():
        raise WorkError('Dieser Upload ist abgelaufen. Bitte neu beginnen.', 410)
    return a


def list_attachments(user, project_id, ticket_id, comment_id=None):
    ticket = ticket_for(user, project_id, ticket_id)
    query = ticket.attachments.filter(state='ready').select_related('ticket')
    if comment_id is not None:
        if not ticket.comments.filter(pk=comment_id).exists(): raise WorkError('Kommentar nicht gefunden.', 404)
        query = query.filter(comment_id=comment_id)
    return {'attachments': [metadata(a) for a in query], 'max_file_bytes': settings.ATTACHMENT_MAX_BYTES}


def start_attachment_upload(user, project_id, ticket_id, filename, size, content_type='application/octet-stream', comment_id=None, sha256=''):
    ticket = ticket_for(user, project_id, ticket_id)
    filename = re.split(r'[/\\]', filename)[-1].strip()
    if not filename or filename in ('.', '..') or len(filename) > 240 or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise WorkError('Bitte einen gültigen Dateinamen mit höchstens 240 Zeichen verwenden.')
    if size > settings.ATTACHMENT_MAX_BYTES:
        raise WorkError(f'Die Datei darf höchstens {settings.ATTACHMENT_MAX_BYTES // 1048576} MiB groß sein.', 413)
    used = ticket.attachments.filter(Q(state='ready') | Q(state='uploading', expires_at__gt=timezone.now())).aggregate(size=Sum('size'))['size'] or 0
    if used + size > settings.ATTACHMENT_TICKET_MAX_BYTES:
        raise WorkError('Das Dateilimit für dieses Ticket ist erreicht.', 413)
    if comment_id is not None and not ticket.comments.filter(pk=comment_id, deleted_at__isnull=True).exists():
        raise WorkError('Kommentar nicht gefunden.', 404)
    content_type = content_type if re.fullmatch(r'[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+', content_type) else 'application/octet-stream'
    a = Attachment.objects.create(ticket=ticket, comment_id=comment_id, uploaded_by=user, filename=filename, size=size,
             content_type=content_type, expected_sha256=sha256, expires_at=timezone.now()+timedelta(hours=24))
    return {**metadata(a), 'chunk_size': CHUNK_SIZE}


def write_chunk(user, project_id, attachment_id, offset, chunk):
    a = attachment_for(user, project_id, attachment_id, ready=False, own=True)
    if a.state != 'uploading': raise WorkError('Dieser Upload ist bereits abgeschlossen.', 409)
    if offset != a.received: raise WorkError(f'Uploadposition geändert. Erwarteter Offset: {a.received}.', 409)
    if len(chunk) > CHUNK_SIZE or a.received + len(chunk) > a.size or not chunk:
        raise WorkError('Ungültige Blockgröße oder überschrittene Dateigröße.')
    path = attachment_path(a)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('r+b' if path.exists() else 'w+b') as output:
        output.seek(a.received); output.truncate(); output.write(chunk)
    path.chmod(0o600)
    a.received += len(chunk)
    a.save(update_fields=['received', 'updated_at'])
    return metadata(a)


def put_attachment_chunk(user, project_id, attachment_id, offset, data_base64):
    try: chunk = base64.b64decode(data_base64, validate=True)
    except (ValueError, binascii.Error): raise WorkError('Ungültiges Base64.') from None
    return write_chunk(user, project_id, attachment_id, offset, chunk)


def complete_attachment_upload(user, project_id, attachment_id):
    a = attachment_for(user, project_id, attachment_id, ready=False, own=True)
    if a.state == 'ready': return metadata(a)
    path = attachment_path(a)
    if a.size == 0 and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700); path.touch(mode=0o600)
    if a.received != a.size or not path.exists() or path.stat().st_size != a.size:
        raise WorkError('Datei ist noch nicht vollständig hochgeladen.', 409)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b''): digest.update(chunk)
    checksum = digest.hexdigest()
    if a.expected_sha256 and checksum != a.expected_sha256:
        raise WorkError('Die Prüfsumme stimmt nicht überein. Bitte den Upload abbrechen und wiederholen.', 409)
    a.sha256 = checksum; a.state = 'ready'
    a.save(update_fields=['sha256', 'state', 'updated_at'])
    event(user, a.ticket.project, a.ticket, 'attachment_created', 'Datei hinzugefügt: ' + a.filename, attachment_id=str(a.pk))
    return metadata(a)


def get_attachment_upload(user, project_id, attachment_id):
    return metadata(attachment_for(user, project_id, attachment_id, ready=False, own=True))


def delete_file_after_commit(a):
    path = attachment_path(a)
    transaction.on_commit(lambda: path.unlink(missing_ok=True))


def cancel_attachment_upload(user, project_id, attachment_id):
    a = attachment_for(user, project_id, attachment_id, ready=False, own=True)
    if a.state != 'uploading': raise WorkError('Zum Entfernen einer fertigen Datei delete_attachment verwenden.')
    a.state = 'deleted'; a.save(update_fields=['state', 'updated_at'])
    delete_file_after_commit(a)
    return {'cancelled': True}


def delete_attachment(user, project_id, attachment_id):
    from .services import owner_only
    a = attachment_for(user, project_id, attachment_id)
    if a.uploaded_by_id != user.pk: owner_only(user, a.ticket.project)
    a.state = 'deleted'; a.save(update_fields=['state', 'updated_at'])
    delete_file_after_commit(a)
    event(user, a.ticket.project, a.ticket, 'attachment_deleted', 'Datei entfernt: ' + a.filename, attachment_id=str(a.pk))
    return {'deleted': True}


def read_attachment_chunk(user, project_id, attachment_id, offset=0, max_bytes=CHUNK_SIZE):
    a = attachment_for(user, project_id, attachment_id)
    if offset > a.size: raise WorkError('Offset liegt hinter dem Dateiende.')
    try:
        with attachment_path(a).open('rb') as stream:
            stream.seek(offset); chunk = stream.read(max_bytes)
    except FileNotFoundError: raise WorkError('Die gespeicherte Datei ist nicht verfügbar.', 503) from None
    return {**metadata(a), 'data_base64': base64.b64encode(chunk).decode(), 'next_offset': offset+len(chunk), 'eof': offset+len(chunk) >= a.size}


def register_operations(register, ID, NAME, TEXT):
    attachment = {'attachment_id': UUID_SCHEMA}
    register(list_attachments, 'Private Ticketdateien lesen, optional auf einen Kommentar beschränkt.', {'ticket_id': ID, 'comment_id': ID}, ['ticket_id'])
    register(start_attachment_upload, 'Privaten Datei-Upload beginnen. Blöcke mit put_attachment_chunk senden; erst complete_attachment_upload macht ihn verfügbar.', {'ticket_id': ID, 'filename': NAME(240), 'size': {'type': 'integer', 'minimum': 0, 'maximum': 1073741824}, 'content_type': NAME(150), 'comment_id': ID, 'sha256': {'type': 'string', 'pattern': r'^(?:[a-f0-9]{64})?$'}}, ['ticket_id', 'filename', 'size'], write=True)
    register(put_attachment_chunk, 'Base64-Block bis 64 KiB am exakten Offset schreiben. get_attachment_upload zeigt die aktuelle Position.', {**attachment, 'offset': {'type': 'integer', 'minimum': 0}, 'data_base64': NAME(87384)}, ['attachment_id', 'offset', 'data_base64'], write=True)
    register(get_attachment_upload, 'Stand des eigenen Datei-Uploads lesen.', attachment, ['attachment_id'])
    register(complete_attachment_upload, 'Upload erst nach Größen- und Prüfsummenprüfung freigeben.', attachment, ['attachment_id'], write=True)
    register(cancel_attachment_upload, 'Eigenen unvollständigen Upload abbrechen.', attachment, ['attachment_id'], write=True)
    register(delete_attachment, 'Datei entfernen (Uploader oder Projekt-/Workspace-Leitung).', attachment, ['attachment_id'], write=True)
    register(read_attachment_chunk, 'Tatsächliche private Datei als Base64-Blöcke lesen. Gesamte sha256 prüfen. Kein öffentlicher Dateilink.', {**attachment, 'offset': {'type': 'integer', 'minimum': 0}, 'max_bytes': {'type': 'integer', 'minimum': 1, 'maximum': CHUNK_SIZE}}, ['attachment_id'])
