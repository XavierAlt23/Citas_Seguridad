import hashlib, json, time, uuid
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import *
from .security import audit, sign, verify_message, IntegrationError

def visible_appointments(user):
    qs = Appointment.objects.select_related('slot__professional__center', 'owner', 'dependent')
    if user.role == 'patient': return qs.filter(owner=user)
    if user.role == 'professional': return qs.filter(slot__professional__account=user)
    if user.role == 'reception': return qs.filter(slot__professional__center_id=user.center_id)
    return qs.none()

def owned(user, queryset, pk):
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        audit(user, 'authorization.denied', pk, 'denied')
        raise PermissionDenied('No tienes permiso para este recurso.')
    return obj

def partner_coverage(insurer_id, payload):
    policy = Policy.objects.filter(pk=payload.get('policy'), insurer_id=insurer_id, active=True).first()
    if not policy or str(policy.owner_id) != str(payload.get('beneficiary')):
        audit(f'insurer:{insurer_id}', 'coverage.denied', result='denied')
        raise PermissionDenied('Solicitud no autorizada.')
    if payload.get('service') != 'consultation':
        raise ValidationError('Prestación no permitida.')
    audit(f'insurer:{insurer_id}', 'coverage.checked', policy.id)
    return {'eligible': True, 'copay': policy.insurer.copay, 'reference': str(uuid.uuid4())}

def check_coverage(policy):
    # Local adapter: same signed contract and tenant checks as the HTTP connector.
    payload = {'policy': str(policy.id), 'beneficiary': str(policy.owner_id), 'service': 'consultation'}
    body = json.dumps(payload, separators=(',', ':')).encode()
    partner, scope, stamp, nonce = f'insurer:{policy.insurer_id}', 'eligibility:check', str(int(time.time())), str(uuid.uuid4())
    key = settings.PARTNER_KEYS[policy.insurer_id - 1]
    verify_message(partner, scope, stamp, nonce, body, sign(key, partner, scope, stamp, nonce, body), key)
    return partner_coverage(policy.insurer_id, payload)

def reserve(user, slot_id, key, policy_id=None, dependent_id=None):
    if user.role != 'patient': raise PermissionDenied()
    try: key = uuid.UUID(str(key))
    except (ValueError, TypeError): raise ValidationError('Clave de operación inválida.')
    digest = hashlib.sha256(json.dumps([str(slot_id), str(policy_id or ''), str(dependent_id or '')]).encode()).hexdigest()
    with transaction.atomic():
        # Serializes retries for this user, then contenders for the same slot.
        User.objects.select_for_update().get(pk=user.pk)
        previous = Appointment.objects.filter(request_key=key).first()
        if previous:
            if previous.owner_id != user.id or previous.request_digest != digest:
                raise ValidationError('La clave de operación ya tiene otro contenido.')
            return previous
        slot = Slot.objects.select_for_update().select_related('professional').get(pk=slot_id)
        now = timezone.now()
        if slot.start <= now: raise ValidationError('Este horario ya pasó.')
        expired = Appointment.objects.filter(slot=slot, status='pending', expires_at__lte=now)
        for old in expired:
            old.status = 'expired'; old.save(update_fields=['status'])
            Payment.objects.filter(appointment=old, status='pending').update(status='expired')
            audit(user, 'appointment.expired', old.id)
        if Appointment.objects.filter(slot=slot, status__in=['pending', 'confirmed']).exists():
            raise ValidationError('El horario acaba de ocuparse. Escoge otro.')
        dependent = None
        if dependent_id:
            dependent = owned(user, Representation.objects.filter(owner=user, active=True, verified_at__isnull=False), dependent_id)
        policy = None
        amount = 4500
        if policy_id:
            policy = owned(user, Policy.objects.filter(owner=user, active=True), policy_id)
            if dependent:
                raise ValidationError('La póliza personal no cubre automáticamente al dependiente. Usa pago particular.')
            amount = check_coverage(policy)['copay']
        appointment = Appointment.objects.create(owner=user, slot=slot, dependent=dependent, request_key=key, request_digest=digest, expires_at=now + timedelta(minutes=15))
        Coverage.objects.create(appointment=appointment, policy=policy, eligible=bool(policy))
        Payment.objects.create(appointment=appointment, amount=amount)
        audit(user, 'appointment.reserved', appointment.pk)
        return appointment

def apply_payment(payload):
    with transaction.atomic():
        # Always lock slot before appointment and payment, as in cancellation/reserve.
        initial = Payment.objects.select_related('appointment').filter(pk=payload.get('payment')).first()
        if not initial: raise ValidationError('Orden inválida.')
        Slot.objects.select_for_update().get(pk=initial.appointment.slot_id)
        appointment = Appointment.objects.select_for_update().get(pk=initial.appointment_id)
        payment = Payment.objects.select_for_update().get(pk=initial.pk)
        if type(payload.get('amount')) is not int or payload['amount'] != payment.amount or payload.get('currency') != payment.currency or payload.get('status') not in ['paid', 'denied']:
            audit('psp', 'payment.mismatch', payment.pk, 'rejected')
            raise ValidationError('Importe, moneda o estado no coincide.')
        try: reference = uuid.UUID(str(payload.get('event')))
        except (ValueError, TypeError): raise ValidationError('Referencia inválida.')
        if payment.status == payload['status'] and payment.psp_reference == reference:
            return payment
        if payment.status != 'pending' or appointment.status != 'pending' or appointment.expires_at <= timezone.now():
            raise ValidationError('La orden expiró o ya se procesó.')
        payment.status = payload['status']; payment.psp_reference = reference
        payment.save(update_fields=['status', 'psp_reference'])
        appointment.status = 'confirmed' if payment.status == 'paid' else 'cancelled'
        appointment.save(update_fields=['status'])
        Notice.objects.create(owner=appointment.owner)
        audit('psp', 'payment.' + payment.status, payment.id)
        return payment

def sandbox_pay(user, appointment_id, approved=True):
    appointment = owned(user, Appointment.objects.filter(owner=user), appointment_id)
    payment = Payment.objects.get(appointment=appointment)
    payload = {'payment': str(payment.pk), 'amount': payment.amount, 'currency': 'USD', 'event': str(uuid.uuid4()), 'status': 'paid' if approved else 'denied'}
    body = json.dumps(payload).encode()
    partner, scope, stamp, nonce = 'psp', 'payments:write', str(int(time.time())), str(uuid.uuid4())
    verify_message(partner, scope, stamp, nonce, body, sign(settings.PSP_KEY, partner, scope, stamp, nonce, body), settings.PSP_KEY)
    return apply_payment(payload)

def cancel(user, appointment_id):
    initial = owned(user, visible_appointments(user), appointment_id)
    if user.role not in ['patient', 'reception']: raise PermissionDenied()
    with transaction.atomic():
        Slot.objects.select_for_update().get(pk=initial.slot_id)
        appointment = Appointment.objects.select_for_update().get(pk=initial.pk)
        if appointment.status in ['cancelled', 'expired']: return appointment
        payment = Payment.objects.select_for_update().get(appointment=appointment)
        if payment.status == 'paid':
            Refund.objects.get_or_create(payment=payment)
            payment.status = 'refunded'
        else: payment.status = 'cancelled'
        payment.save(update_fields=['status'])
        appointment.status = 'cancelled'; appointment.save(update_fields=['status'])
        Notice.objects.create(owner=appointment.owner)
        audit(user, 'appointment.cancelled', appointment.id)
        return appointment
