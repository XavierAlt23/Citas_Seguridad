"""Run database tests using owner credentials; never grants them to the web process."""
import os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT)
env=dict(os.environ,DB_USER=os.environ.get('OWNER_USER','postgres'),DB_PASSWORD=os.environ.get('OWNER_PASSWORD',(ROOT/'.local/db-owner-password').read_text().strip()))
subprocess.run([sys.executable,'manage.py','check','--deploy'],check=True)
subprocess.run([sys.executable,'manage.py','makemigrations','--check','--dry-run'],check=True)
subprocess.run([sys.executable,'manage.py','test','app','--noinput','--testrunner','app.runner.EvidenceRunner','-v','2'],env=env,check=True)
