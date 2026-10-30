from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.sessions.models import Session
from django.utils import timezone
from app.models import *
from app.security import audit, fingerprint

class Command(BaseCommand):
    help = 'Expira cupos, disocia cuentas vencidas y elimina datos operativos sin obligación de conservación.'
    def handle(self, *args, **options):
        now = timezone.now(); expired = 0; erased = 0
        ids = list(Appointment.objects.filter(status='pending', expires_at__lte=now).values_list('pk', 'slot_id')[:1000])
        for pk, slot in ids:
            with transaction.atomic():
                Slot.objects.select_for_update().get(pk=slot)
                a = Appointment.objects.select_for_update().get(pk=pk)
                if a.status != 'pending' or a.expires_at > now: continue
                a.status='expired'; a.save(update_fields=['status'])
                Payment.objects.filter(appointment=a,status='pending').update(status='expired')
                audit('scheduler','appointment.expired',a.pk); expired += 1
        for user in User.objects.filter(closed_at__lte=now-timedelta(days=365), is_active=False).exclude(first_name='Disociado').exclude(legalhold__isnull=False):
            with transaction.atomic():
                digest = fingerprint(user.pk)
                Erasure.objects.get_or_create(subject_digest=digest)
                user.first_name='Disociado'; user.last_name=''; user.email=''; user.username='erased-'+str(user.pk); user.mfa_cipher=''; user.set_unusable_password(); user.save()
                Policy.objects.filter(owner=user).update(reference_cipher='',active=False)
                Representation.objects.filter(owner=user).update(name='Disociado',age=0,evidence_digest='',active=False)
                audit('scheduler','retention.disassociated',digest); erased += 1
        # Financial records are on hold until an applicable accounting retention is defined.
        old = Appointment.objects.filter(created_at__lt=now-timedelta(days=730),status__in=['cancelled','expired']).exclude(owner__legalhold__isnull=False).exclude(payment__status__in=['paid','refunded']).exclude(payment__refund__isnull=False)
        for a in old[:1000]:
            audit('scheduler','retention.appointment_deleted',a.pk); a.delete()
        Notice.objects.filter(created_at__lt=now-timedelta(days=30)).delete()
        EventNonce.objects.filter(created_at__lt=now-timedelta(days=1)).delete()
        MFAChallenge.objects.filter(expires_at__lt=now-timedelta(days=1)).delete()
        RateBucket.objects.filter(until__lt=now-timedelta(days=1)).delete()
        Session.objects.filter(expire_date__lt=now).delete()
        self.stdout.write(f'Mantenimiento: {expired} cupos expirados; {erased} cuentas disociadas.')
