"""Owner-only bounded audit retention. Runtime role cannot perform this operation."""
import os, sys, hmac, hashlib
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.utils import timezone
from django.core.management import call_command
from app.security import audit
import psycopg
db=settings.DATABASES['default']
call_command('verify_audit',verbosity=0)
with psycopg.connect(host=db['HOST'],port=db['PORT'],dbname=db['NAME'],user=os.environ.get('OWNER_USER','postgres'),password=os.environ.get('OWNER_PASSWORD',(ROOT/'.local/db-owner-password').read_text().strip())) as conn:
    conn.execute('SELECT pg_advisory_xact_lock(812031)')
    cutoff=timezone.now()-timedelta(days=365)
    last=conn.execute('SELECT id,digest FROM app_audit WHERE created_at < %s AND id < COALESCE((SELECT min(id) FROM app_audit WHERE created_at >= %s),9223372036854775807) ORDER BY id DESC LIMIT 1',[cutoff,cutoff]).fetchone()
    if last:
        signature=hmac.new(settings.AUDIT_KEY.encode(),f'{last[0]}:{last[1]}'.encode(),hashlib.sha256).hexdigest()
        conn.execute('INSERT INTO app_auditcheckpoint (id,last_id,last_digest,signature) VALUES (1,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET last_id=EXCLUDED.last_id,last_digest=EXCLUDED.last_digest,signature=EXCLUDED.signature',[*last,signature])
        conn.execute('ALTER TABLE app_audit DISABLE TRIGGER protect_audit')
        conn.execute('DELETE FROM app_audit WHERE id <= %s',[last[0]])
        conn.execute('ALTER TABLE app_audit ENABLE TRIGGER protect_audit')
audit('retention-owner','audit.retention_completed')
call_command('verify_audit',verbosity=0)
