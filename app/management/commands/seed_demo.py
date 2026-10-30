import secrets
from datetime import timedelta
from pathlib import Path
import pyotp
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from app.models import *
from app.security import encrypt, audit

class Command(BaseCommand):
    help = 'Crea únicamente datos sintéticos, sin sobrescribir cuentas existentes.'
    @transaction.atomic
    def handle(self, *args, **options):
        centers = [Center.objects.get_or_create(id=i, defaults={'name': f'Centro {i:02d} · ' + ['La Carolina', 'El Bosque', 'Cumbayá', 'Los Chillos'][(i-1)%4]})[0] for i in range(1,21)]
        insurers = [Insurer.objects.get_or_create(id=i, defaults={'name': name + ' (simulada)', 'copay': 1000 + i*250})[0] for i,name in enumerate(['Andina', 'Horizonte', 'Vital', 'Equilibrio', 'Familia'], 1)]
        accounts = [('paciente.a','patient',None,None),('paciente.b','patient',None,None),('medico.a','professional',centers[0],None),('medico.b','professional',centers[1],None),('recepcion.a','reception',centers[0],None),('recepcion.b','reception',centers[1],None),('operador.a','operator',None,None),('operador.b','operator',None,None)]
        accounts += [(f'seguro.{i}', 'insurer', None, insurer) for i,insurer in enumerate(insurers,1)]
        new_access = []
        for name,role,center,insurer in accounts:
            if User.objects.filter(username=name).exists(): continue
            password = secrets.token_urlsafe(18)
            user = User.objects.create_user(username=name, password=password, first_name=name.replace('.', ' ').title(), email=name+'@example.invalid', role=role, center=center, insurer=insurer, mfa_cipher=encrypt(pyotp.random_base32()), mfa_ready=True)
            new_access.append(f'| {name} | {password} | {role} |')
            audit('bootstrap', 'account.provisioned', user.pk)
        specialties = ['Medicina general', 'Pediatría', 'Dermatología', 'Cardiología', 'Oftalmología', 'Traumatología']
        for i in range(1,151):
            prof, _ = Professional.objects.get_or_create(id=i, defaults={'name': f'Dra. / Dr. Profesional {i:03d}', 'center': centers[(i-1)%20], 'specialty': specialties[(i-1)%6]})
            if i in [1,2]:
                prof.account = User.objects.get(username='medico.' + ('a' if i==1 else 'b')); prof.save()
            tomorrow = (timezone.localtime() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            for day in range(1,5):
                for hour in [0,2]: Slot.objects.get_or_create(professional=prof, start=tomorrow+timedelta(days=day-1,hours=hour))
        for n,insurer in enumerate(insurers):
            patient = User.objects.get(username='paciente.a' if n%2==0 else 'paciente.b')
            if not Policy.objects.filter(owner=patient, insurer=insurer).exists(): Policy.objects.create(owner=patient, insurer=insurer, reference_cipher=encrypt(f'DEMO-POLIZA-{n+1:03d}'))
        if new_access:
            path = Path('.local/access.md')
            fd = __import__('os').open(path, __import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_APPEND, 0o600)
            with __import__('os').fdopen(fd,'a') as f:
                f.write('# Accesos sintéticos locales — no publicar\n\n| Usuario | Contraseña | Rol |\n|---|---|---|\n'+'\n'.join(new_access)+'\n\nMFA: `.venv/bin/python manage.py demo_code USUARIO`\n')
        self.stdout.write('Datos sintéticos preparados; credenciales disponibles solo en .local/access.md.')
