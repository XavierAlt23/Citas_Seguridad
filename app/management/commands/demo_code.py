from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from app.models import User, MFAChallenge
from app.security import decrypt, audit
from app.demo_auth import DEMO_USERNAMES

class Command(BaseCommand):
    help = 'Muestra el código de un solo uso del inicio pendiente de una cuenta sintética.'
    def add_arguments(self, parser): parser.add_argument('username')
    def handle(self, username, **options):
        if username not in DEMO_USERNAMES: raise CommandError('Solo cuentas sintéticas preaprovisionadas.')
        user = User.objects.get(username=username)
        challenge = MFAChallenge.objects.filter(user=user, consumed_at=None, revoked_at=None, expires_at__gt=timezone.now()).order_by('-created_at').first()
        if challenge is None:
            raise CommandError('Primero inicia sesión con usuario y contraseña. Cada nuevo inicio crea un código distinto; el anterior deja de servir.')
        audit('local-console', 'demo.mfa_generated', challenge.pk)
        self.stdout.write(decrypt(challenge.code_cipher))
