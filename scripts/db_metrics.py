"""Read-only capacity evidence: current DB connections, size and public-query plan."""
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.db import connection
from django.utils import timezone
with connection.cursor() as cursor:
    cursor.execute('SELECT pg_database_size(current_database())');size=cursor.fetchone()[0]
    cursor.execute('SELECT state,count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY state');states=dict(cursor.fetchall())
    cursor.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT s.id,p.name,p.specialty,c.name,s.start FROM app_slot s JOIN app_professional p ON p.id=s.professional_id JOIN app_center c ON c.id=p.center_id WHERE s.start>%s ORDER BY s.start,p.name LIMIT 60',[timezone.now()]);plan=cursor.fetchone()[0]
result={'database_bytes':size,'connection_states_snapshot':states,'public_query_plan':plan,'note':'Consulta pública base con joins/fecha/orden; no equivale al EXPLAIN de todos los filtros y exclusiones ORM. Snapshot, no pico durante carga.','run_at':timezone.now().isoformat()}
(ROOT/'evidence/db-metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps({'database_bytes':size,'connection_states_snapshot':states,'plan_recorded':True},indent=2))
