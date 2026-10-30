"""One-time login challenges for the explicitly provisioned synthetic accounts."""
import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import User, MFAChallenge
from .security import encrypt, fingerprint, audit

DEMO_USERNAMES = frozenset(['paciente.a','paciente.b','medico.a','medico.b','recepcion.a','recepcion.b','operador.a','operador.b',*[f'seguro.{i}' for i in range(1,6)]])

def uses_login_challenge(user):
    return user.username in DEMO_USERNAMES

def create_login_challenge(user, binding):
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        previous = MFAChallenge.objects.filter(user=user).order_by('-created_at').first()
        now = timezone.now()
        MFAChallenge.objects.filter(user=user, consumed_at=None, revoked_at=None).update(revoked_at=now, code_cipher='')
        while True:
            code = f'{secrets.randbelow(1000000):06d}'
            digest = fingerprint('login-code:' + code)
            if previous is None or digest != previous.code_digest:
                break
        challenge = MFAChallenge.objects.create(user=user, code_cipher=encrypt(code), code_digest=digest, binding_digest=fingerprint(binding), expires_at=now+timedelta(minutes=5))
        audit(user, 'mfa.challenge_created', challenge.pk)
        return challenge
