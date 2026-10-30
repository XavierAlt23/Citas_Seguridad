"""Generate local secrets once, then initialize Docker/PostgreSQL and Django."""
import argparse, datetime, ipaddress, os, secrets, subprocess, sys
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.fernet import Fernet
from cryptography.x509.oid import NameOID
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
local = ROOT / '.local'; local.mkdir(exist_ok=True, mode=0o700)
local.chmod(0o700)

def private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(text)

if not (ROOT / '.env').exists():
    values = {'SECRET_KEY': secrets.token_urlsafe(64), 'FIELD_KEY': Fernet.generate_key().decode(), 'AUDIT_KEY': secrets.token_urlsafe(48), 'PSP_KEY': secrets.token_urlsafe(48), 'DB_NAME': 'consultas', 'DB_USER': 'consultas_app', 'DB_PASSWORD': secrets.token_urlsafe(32), 'DB_HOST': '127.0.0.1', 'DB_PORT': '55432'}
    values.update({f'PARTNER_KEY_{i}': secrets.token_urlsafe(48) for i in range(1, 6)})
    private(ROOT / '.env', '\n'.join(f'{k}={v}' for k,v in values.items()) + '\n')
if not (local / 'db-owner-password').exists(): private(local / 'db-owner-password', secrets.token_urlsafe(36))
if not (local / 'backup.key').exists(): private(local / 'backup.key', Fernet.generate_key().decode())
if not (local / 'tls-key.pem').exists():
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=365)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False).sign(key, hashes.SHA256())
    private(local / 'tls-key.pem', key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
    private(local / 'tls-cert.pem', cert.public_bytes(serialization.Encoding.PEM).decode())
if '--secrets-only' in sys.argv:
    print('Secretos y certificado local preparados.'); sys.exit(0)
if '--existing-postgres' not in sys.argv:
    subprocess.run(['docker', 'compose', 'up', '-d', '--wait', 'db'], check=True)
sys.path.insert(0, str(ROOT)); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
import psycopg
from psycopg import sql
db = settings.DATABASES['default']
owner = os.environ.get('OWNER_USER', 'postgres')
owner_password = os.environ.get('OWNER_PASSWORD', (local / 'db-owner-password').read_text().strip())
with psycopg.connect(host=db['HOST'], port=db['PORT'], dbname=db['NAME'], user=owner, password=owner_password, autocommit=True) as conn:
    if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', [db['USER']]).fetchone():
        conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(db['USER']), sql.Literal(db['PASSWORD'])))
    conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
env = dict(os.environ, DB_USER=owner, DB_PASSWORD=owner_password)
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], env=env, check=True)
with psycopg.connect(host=db['HOST'], port=db['PORT'], dbname=db['NAME'], user=owner, password=owner_password, autocommit=True) as conn:
    role = sql.Identifier(db['USER'])
    conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(db['NAME']), role))
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(role))
    conn.execute(sql.SQL('REVOKE UPDATE, DELETE ON app_audit FROM {}').format(role))
    conn.execute(sql.SQL('REVOKE INSERT, UPDATE, DELETE ON app_auditcheckpoint FROM {}').format(role))
subprocess.run([sys.executable, 'manage.py', 'seed_demo'], check=True)
subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'], check=True)
print('Listo. Accesos privados: .local/access.md. Inicia con: bash scripts/run.sh')
