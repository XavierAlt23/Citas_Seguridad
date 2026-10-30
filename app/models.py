import uuid
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser

class Center(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=60, default='Quito')

class Insurer(models.Model):
    name = models.CharField(max_length=80)
    copay = models.PositiveIntegerField(default=1500)

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, default='patient', choices=[(x, x) for x in ['patient', 'professional', 'reception', 'insurer', 'operator']])
    center = models.ForeignKey(Center, null=True, blank=True, on_delete=models.PROTECT)
    insurer = models.ForeignKey(Insurer, null=True, blank=True, on_delete=models.PROTECT)
    mfa_cipher = models.TextField(blank=True)
    mfa_ready = models.BooleanField(default=False)
    mfa_last = models.BigIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)

class Professional(models.Model):
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=80, db_index=True)
    center = models.ForeignKey(Center, on_delete=models.PROTECT)
    account = models.OneToOneField(User, null=True, blank=True, on_delete=models.PROTECT)

class Slot(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.PROTECT)
    start = models.DateTimeField(db_index=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['professional', 'start'], name='unique_professional_slot')]

class Representation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    age = models.PositiveSmallIntegerField()
    evidence_digest = models.CharField(max_length=64)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='verified_links')
    verified_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(age__lte=120), name='valid_age')]

class Policy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT)
    reference_cipher = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Appointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    slot = models.ForeignKey(Slot, on_delete=models.PROTECT)
    dependent = models.ForeignKey(Representation, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, default='pending', choices=[(x, x) for x in ['pending', 'confirmed', 'cancelled', 'expired']])
    request_key = models.UUIDField(unique=True)
    request_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['slot'], condition=Q(status__in=['pending', 'confirmed']), name='one_live_booking_per_slot')]

class Coverage(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, null=True, on_delete=models.PROTECT)
    eligible = models.BooleanField(default=False)
    reference = models.UUIDField(default=uuid.uuid4)

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=16, default='pending')
    psp_reference = models.UUIDField(null=True, unique=True)
    currency = models.CharField(max_length=3, default='USD')

class Refund(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT)
    reference = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EventNonce(models.Model):
    partner = models.CharField(max_length=30)
    nonce = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['partner', 'nonce'], name='unique_partner_nonce')]

class Audit(models.Model):
    actor = models.CharField(max_length=64)
    action = models.CharField(max_length=70)
    object_id = models.CharField(max_length=100, blank=True)
    result = models.CharField(max_length=30, default='ok')
    created_at = models.DateTimeField()
    previous = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)

class Notice(models.Model):
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    text = models.CharField(max_length=150, default='Tienes una actualización. Ingresa a tu cuenta para consultarla.')
    created_at = models.DateTimeField(auto_now_add=True)

class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    until = models.DateTimeField()

class RoleChange(models.Model):
    target = models.ForeignKey(User, on_delete=models.PROTECT, related_name='role_changes')
    proposed_role = models.CharField(max_length=20)
    center = models.ForeignKey(Center, null=True, on_delete=models.PROTECT)
    insurer = models.ForeignKey(Insurer, null=True, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='role_requests')
    approved_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name='role_approvals')
    created_at = models.DateTimeField(auto_now_add=True)

class LegalHold(models.Model):
    owner = models.OneToOneField(User, on_delete=models.PROTECT)
    reason_code = models.CharField(max_length=50)

class Erasure(models.Model):
    subject_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditCheckpoint(models.Model):
    last_id = models.BigIntegerField(default=0)
    last_digest = models.CharField(max_length=64, default='0'*64)
    signature = models.CharField(max_length=64)

class MFAChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code_cipher = models.TextField()
    code_digest = models.CharField(max_length=64)
    binding_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
