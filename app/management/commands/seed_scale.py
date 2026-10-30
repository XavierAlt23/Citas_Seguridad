from django.core.management.base import BaseCommand
from app.models import User

class Command(BaseCommand):
    help = 'Completa 40.000 pacientes ficticios inactivos para medir volumen; no borra datos.'
    def handle(self, *args, **options):
        count = User.objects.filter(role='patient').count()
        remaining = max(0, 40000-count)
        offset=User.objects.filter(username__startswith='scale-').count()
        for start in range(0,remaining,1000):
            User.objects.bulk_create([User(username=f'scale-{offset+i:06d}',password='!unusable',first_name='Sintético',role='patient',is_active=False) for i in range(start,min(start+1000,remaining))],ignore_conflicts=True)
        self.stdout.write(f'Pacientes: {User.objects.filter(role="patient").count()}')
