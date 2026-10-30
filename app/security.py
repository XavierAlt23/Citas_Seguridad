import hashlib, hmac, json, time
from datetime import timedelta
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction, connection, IntegrityError
from django.utils import timezone
from .models import Audit, AuditCheckpoint, RateBucket, EventNonce

def encrypt(value):
    return Fernet(settings.FIELD_KEY.encode()).encrypt(value.encode()).decode()

def decrypt(value):
    return Fernet(settings.FIELD_KEY.encode()).decrypt(value.encode()).decode()

def fingerprint(value):
    return hmac.new(settings.AUDIT_KEY.encode(), str(value).encode(), hashlib.sha256).hexdigest()

def audit_payload(actor, action, object_id, result, created_at, previous):
    return json.dumps([actor, action, object_id, result, created_at.isoformat(), previous], separators=(',', ':'))

def audit(actor, action, obj='', result='ok'):
    actor = str(getattr(actor, 'pk', actor) or 'anonymous')[:64]
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute('SELECT pg_advisory_xact_lock(812031)')
        checkpoint = AuditCheckpoint.objects.filter(pk=1).first()
        previous = Audit.objects.order_by('-id').values_list('digest', flat=True).first() or (checkpoint.last_digest if checkpoint else '0' * 64)
        now = timezone.now()
        obj = str(obj)[:100]
        payload = audit_payload(actor, action, obj, result, now, previous)
        digest = hmac.new(settings.AUDIT_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return Audit.objects.create(actor=actor, action=action, object_id=obj, result=result, created_at=now, previous=previous, digest=digest)

def limited(key, maximum=120, seconds=60):
    key = fingerprint(key)
    now = timezone.now()
    with transaction.atomic():
        RateBucket.objects.get_or_create(key=key, defaults={'until': now + timedelta(seconds=seconds)})
        bucket = RateBucket.objects.select_for_update().get(key=key)
        if bucket.until <= now:
            bucket.count = 0
            bucket.until = now + timedelta(seconds=seconds)
        bucket.count += 1
        bucket.save()
        return bucket.count > maximum

def sign(key, partner, scope, timestamp, nonce, body):
    canonical = f'{partner}\n{scope}\n{timestamp}\n{nonce}\n'.encode() + body
    return hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()

class IntegrationError(Exception):
    pass

def verify_message(partner, scope, timestamp, nonce, body, signature, key):
    try:
        valid_time = abs(time.time() - int(timestamp)) <= 60
    except (ValueError, TypeError):
        valid_time = False
    if not valid_time or not nonce or len(nonce) > 100 or not hmac.compare_digest(sign(key, partner, scope, str(timestamp), nonce, body), signature):
        audit(partner, 'integration.rejected', result='invalid_signature')
        raise IntegrationError('Firma o fecha inválida.')
    try:
        with transaction.atomic():
            EventNonce.objects.create(partner=partner, nonce=nonce)
    except IntegrityError:
        audit(partner, 'integration.replay', result='rejected')
        raise IntegrationError('Evento repetido.')
