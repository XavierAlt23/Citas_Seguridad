import hashlib, hmac
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from app.models import Audit, AuditCheckpoint
from app.security import audit_payload

class Command(BaseCommand):
    help = 'Verifica orden e integridad HMAC de toda la cadena de auditoría.'
    def handle(self, *args, **options):
        previous = '0'*64; count = 0
        checkpoint = AuditCheckpoint.objects.filter(pk=1).first()
        if checkpoint:
            expected = hmac.new(settings.AUDIT_KEY.encode(), f'{checkpoint.last_id}:{checkpoint.last_digest}'.encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,checkpoint.signature): raise CommandError('Ancla de retención alterada.')
            previous = checkpoint.last_digest
        for event in Audit.objects.order_by('id').iterator():
            payload = audit_payload(event.actor,event.action,event.object_id,event.result,event.created_at,event.previous)
            expected = hmac.new(settings.AUDIT_KEY.encode(),payload.encode(),hashlib.sha256).hexdigest()
            if event.previous != previous or not hmac.compare_digest(event.digest, expected): raise CommandError(f'Cadena alterada en evento {event.id}.')
            previous = event.digest; count += 1
        self.stdout.write(f'OK: {count} eventos; ancla final {previous}')
