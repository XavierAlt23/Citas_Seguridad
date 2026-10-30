"""Local maintenance loop. Its errors stay visible; no cloud services required."""
import subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
last_backup = -3600
try:
    while True:
        subprocess.run([sys.executable, 'manage.py', 'maintenance'], cwd=ROOT, check=False)
        if time.monotonic() - last_backup >= 3600:
            subprocess.run([sys.executable, 'scripts/audit_retention.py'], cwd=ROOT, check=False)
            backup=subprocess.run([sys.executable, 'scripts/backup.py', 'backup'], cwd=ROOT, check=False)
            if backup.returncode==0: last_backup = time.monotonic()
        time.sleep(60)
except KeyboardInterrupt:
    pass
