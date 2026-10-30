"""Encrypted pg_dump and non-destructive restore drill in a NEW database."""
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT); sys.path.insert(0,str(ROOT)); os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from cryptography.fernet import Fernet
import psycopg
from psycopg import sql

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['backup','restore-drill']); parser.add_argument('--file'); parser.add_argument('--native',action='store_true',help='Solo validación cuando Docker no está disponible'); args=parser.parse_args()
    db=settings.DATABASES['default']; local=ROOT/'.local'
    folder=Path(os.environ.get('BACKUP_DIR',str(local/'backups'))); folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    cipher=Fernet((local/'backup.key').read_bytes().strip())
    env=dict(os.environ,PGPASSWORD=os.environ.get('OWNER_PASSWORD',(local/'db-owner-password').read_text().strip()))
    user=os.environ.get('OWNER_USER','postgres')
    def command(binary, database, *rest):
        if args.native: return ['/usr/lib/postgresql/16/bin/'+binary,'-h',db['HOST'],'-p',str(db['PORT']),'-U',user,'-d',database,*rest]
        return ['docker','compose','exec','-T','db',binary,'-U','postgres','-d',database,*rest]
    evidence=ROOT/'evidence'; evidence.mkdir(exist_ok=True)
    if args.action=='backup':
        started=time.perf_counter()
        raw=subprocess.run(command('pg_dump',db['NAME'],'-Fc','--no-owner','--no-acl'),env=env,check=True,capture_output=True).stdout
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path=folder/(stamp+'.dump.fernet'); path.write_bytes(cipher.encrypt(raw)); path.chmod(0o600)
        info={'file':str(path),'created_at':datetime.now(timezone.utc).isoformat(),'sha256_plaintext':hashlib.sha256(raw).hexdigest(),'seconds':round(time.perf_counter()-started,3),'database':db['NAME'],'mode':'native-validation' if args.native else 'docker'}
        path.with_suffix('.json').write_text(json.dumps(info,indent=2)); print(json.dumps(info,indent=2))
        for old in folder.glob('*.dump.fernet'):
            if time.time()-old.stat().st_mtime>86400 and old!=path:
                old.unlink(); old.with_suffix('.json').unlink(missing_ok=True)
        return
    path=Path(args.file) if args.file else max(folder.glob('*.dump.fernet'),key=lambda p:p.stat().st_mtime,default=None)
    if not path: raise SystemExit('Primero crea una copia.')
    started=time.perf_counter(); raw=cipher.decrypt(path.read_bytes())
    metadata=json.loads(path.with_suffix('.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=metadata['sha256_plaintext']: raise SystemExit('Checksum no coincide.')
    staging='restore_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    conn=psycopg.connect(host=db['HOST'],port=db['PORT'],dbname='postgres',user=user,password=env['PGPASSWORD'],autocommit=True)
    conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(staging)))
    subprocess.run(command('pg_restore',staging,'--no-owner','--no-acl','--exit-on-error'),input=raw,env=env,check=True,capture_output=True)
    with psycopg.connect(host=db['HOST'],port=db['PORT'],dbname=staging,user=user,password=env['PGPASSWORD']) as restored:
        rows={table:restored.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] for table in ['app_user','app_appointment','app_payment','app_refund','app_coverage','app_audit']}
        # Replay disassociation tombstones created since the backup; never return old PII to service.
        from app.models import Erasure
        from app.security import fingerprint
        tombstones=set(Erasure.objects.values_list('subject_digest',flat=True))
        for row in restored.execute('SELECT id FROM app_user').fetchall():
            if fingerprint(row[0]) in tombstones:
                restored.execute("UPDATE app_user SET first_name='Disociado',last_name='',email='',username=%s,mfa_cipher='',password='!erased',is_active=false WHERE id=%s",['erased-'+str(row[0]),row[0]])
                restored.execute("UPDATE app_policy SET reference_cipher='',active=false WHERE owner_id=%s",[row[0]])
                restored.execute("UPDATE app_representation SET name='Disociado',age=0,evidence_digest='',active=false WHERE owner_id=%s",[row[0]])
        restored.execute('DELETE FROM django_session')
    # Validate the restored audit and apply expired retention BEFORE any traffic.
    restore_env=dict(env,DB_NAME=staging,DB_USER=user,DB_PASSWORD=env['PGPASSWORD'])
    for cmd in ['verify_audit','maintenance']:
        subprocess.run([sys.executable,'manage.py',cmd],env=restore_env,check=True,capture_output=True)
    subprocess.run([sys.executable,'scripts/audit_retention.py'],env=restore_env,check=True,capture_output=True)
    seconds=round(time.perf_counter()-started,3)
    rpo=round((datetime.now(timezone.utc)-datetime.fromisoformat(metadata['created_at'])).total_seconds(),3)
    result={'staging_database':staging,'restored_rows':rows,'checksum_verified':True,'audit_verified':True,'sessions_revoked':True,'tombstones_applied':len(tombstones),'rto_seconds':seconds,'backup_age_seconds_rpo_upper_bound':rpo,'rto_target_seconds':14400,'rpo_target_seconds':3600,'within_rto':seconds<=14400,'within_rpo':rpo<=3600,'note':'Ensayo sobre base NUEVA; no simula pérdida del host ni alta disponibilidad.','mode':'native-validation' if args.native else 'docker'}
    (evidence/'restore.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
    conn.close()

if __name__=='__main__': main()
