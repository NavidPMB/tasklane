from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from modules.work.attachments import delete_file_after_commit
from modules.work.models import Attachment, ClickUpImportBatch


class Command(BaseCommand):
    help = 'Abgelaufene unvollständige Uploads und Importpläne bereinigen. Ohne --apply nur Vorschau.'

    def add_arguments(self, parser): parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        pending = Attachment.objects.filter(state='uploading', expires_at__lt=timezone.now())
        batches = ClickUpImportBatch.objects.filter(expires_at__lt=timezone.now())
        self.stdout.write(f'{pending.count()} abgelaufene Uploads, {batches.count()} abgelaufene ClickUp-Prüfstände.')
        if not options['apply']:
            self.stdout.write('Vorschau; zum Ausführen --apply angeben.'); return
        for pk in list(pending.values_list('pk', flat=True)):
            with transaction.atomic():
                item = Attachment.objects.select_for_update().filter(pk=pk, state='uploading', expires_at__lt=timezone.now()).first()
                if item:
                    item.state = 'deleted'; item.save(update_fields=['state']); delete_file_after_commit(item)
        batches.delete()
        self.stdout.write(self.style.SUCCESS('Bereinigung abgeschlossen.'))
