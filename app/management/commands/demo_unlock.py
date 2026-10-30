from django.core.management.base import BaseCommand, CommandError
from app.models import User, RateBucket
from app.security import audit, fingerprint
from app.demo_auth import DEMO_USERNAMES

class Command(BaseCommand):
    help = 'Desbloqueo auditado desde consola local, exclusivo para cuentas sintéticas.'
    def add_arguments(self, parser): parser.add_argument('username')
    def handle(self, username, **options):
        if username not in DEMO_USERNAMES: raise CommandError('Solo cuentas sintéticas preaprovisionadas.')
        user = User.objects.get(username=username)
        keys = ['mfa:'+str(user.pk), 'login:user:'+username, 'login:ip:127.0.0.1']
        RateBucket.objects.filter(key__in=[fingerprint(key) for key in keys]).delete()
        audit('local-console', 'demo.auth_unlocked', user.pk)
        self.stdout.write('Cuenta sintética desbloqueada. Vuelve a iniciar sesión con usuario y contraseña.')
