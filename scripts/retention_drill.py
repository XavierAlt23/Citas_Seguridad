"""Synthetic overdue account: backup BEFORE purge, restore AFTER purge, verify no resurrection."""
import json, os, subprocess, sys, uuid
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.core.management import call_command
from django.utils import timezone
from app.models import User,Policy,Insurer
from app.security import encrypt,audit
import psycopg
from django.conf import settings

user=User.objects.create_user(username='retention-drill-'+uuid.uuid4().hex[:12],first_name='Persona Ficticia',email='sintetico@example.invalid',role='patient',is_active=False,closed_at=timezone.now()-timedelta(days=370))
Policy.objects.create(owner=user,insurer=Insurer.objects.get(pk=1),reference_cipher=encrypt('DEMO-RETENCION'))
audit('retention-drill','retention.synthetic_created',user.pk)
extra=['--native'] if '--native' in sys.argv else []
subprocess.run([sys.executable,'scripts/backup.py','backup',*extra],check=True)
call_command('maintenance')
subprocess.run([sys.executable,'scripts/backup.py','restore-drill',*extra],check=True)
report=json.loads((ROOT/'evidence/restore.json').read_text());db=settings.DATABASES['default']
with psycopg.connect(host=db['HOST'],port=db['PORT'],dbname=report['staging_database'],user=os.environ.get('OWNER_USER','postgres'),password=os.environ.get('OWNER_PASSWORD',(ROOT/'.local/db-owner-password').read_text().strip())) as conn:
    row=conn.execute('SELECT first_name,email,is_active FROM app_user WHERE id=%s',[user.pk]).fetchone()
    policy=conn.execute('SELECT reference_cipher,active FROM app_policy WHERE owner_id=%s',[user.pk]).fetchone()
    assert row==('Disociado','',False),row
    assert policy==('',False),policy
result={'passed':True,'subject':'synthetic overdue account','backup_before_disassociation':True,'restore_after_disassociation':True,'restored_contact_empty':True,'restored_policy_empty':True,'restored_account_inactive':True,'staging_database':report['staging_database']}
(ROOT/'evidence/retention-restore.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
