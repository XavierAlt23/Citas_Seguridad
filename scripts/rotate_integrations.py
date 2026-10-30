"""Rotate simulator integration keys without printing them. Restart web afterwards."""
import os, secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
path=ROOT/'.env'
values={}
for line in path.read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key,value=line.split('=',1);values[key]=value
for key in ['PSP_KEY',*[f'PARTNER_KEY_{i}' for i in range(1,6)]]: values[key]=secrets.token_urlsafe(48)
temporary=ROOT/'.local/rotated-env.tmp'
fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write('\n'.join(f'{key}={value}' for key,value in values.items())+'\n');f.flush();os.fsync(f.fileno())
os.replace(temporary,path)
print('Claves de los cinco seguros y PSP renovadas. Reinicia la web y el planificador; mensajes con claves anteriores serán rechazados. Las claves de cifrado/auditoría no se modificaron.')
