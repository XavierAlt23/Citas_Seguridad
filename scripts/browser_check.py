"""End-to-end synthetic booking; captures desktop and mobile without secrets."""
import json, os, sys, time, io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from app.models import User,RateBucket,Representation
from app.security import decrypt,fingerprint
from django.db import connections
from django.core.management import call_command
import pyotp
from playwright.sync_api import sync_playwright
access={}
for line in (ROOT/'.local/access.md').read_text().splitlines():
    if line.startswith('| ') and line.count('|')>=4:
        columns=[x.strip() for x in line.split('|')]
        access[columns[1]]=columns[2]
out=ROOT/'evidence/screenshots';out.mkdir(parents=True,exist_ok=True)
errors=[]; results=[]
RateBucket.objects.filter(key=fingerprint('ip:127.0.0.1')).delete()

def db_call(fn):
    # Playwright sync API runs an internal event loop; isolate synchronous ORM work.
    def run():
        try: return fn()
        finally: connections.close_all()
    with ThreadPoolExecutor(max_workers=1) as pool: return pool.submit(run).result()

with sync_playwright() as p:
    options={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
    if Path('/opt/brave.com/brave/brave').exists(): options['executable_path']='/opt/brave.com/brave/brave'
    browser=p.chromium.launch(**options)
    def context():
        return browser.new_context(ignore_https_errors=False,viewport={'width':1440,'height':1000},locale='es-EC',reduced_motion='reduce')
    def login(page,name):
        page.goto('https://localhost:8443/login/')
        page.locator('#id_username').fill(name);page.locator('#id_password').fill(access[name]);page.get_by_role('button',name='Continuar',exact=True).click();page.wait_for_url('**/mfa/')
        def read_code():
            output=io.StringIO();call_command('demo_code',name,stdout=output);return output.getvalue().strip()
        code=db_call(read_code)
        page.get_by_label('Código de verificación').fill(code);page.get_by_role('button',name='Verificar y entrar').click();page.wait_for_url('**/panel/')
    ctx=context();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    response=page.goto('https://localhost:8443/');assert response.status==200
    page.screenshot(path=str(out/'desktop.png'))
    assert page.locator('tbody tr').count()>0
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'mobile.png'))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Desbordamiento horizontal'
    page.set_viewport_size({'width':1440,'height':1000});login(page,'paciente.a')
    page.screenshot(path=str(out/'patient.png'))
    page.goto('https://localhost:8443/');page.get_by_role('link',name='Elegir horario').first.click()
    select=page.locator('#policy option');page.locator('#policy').select_option(select.nth(1).get_attribute('value'))
    page.get_by_role('button',name='Validar cobertura y continuar').click();page.wait_for_url('**/appointments/*/')
    page.get_by_role('button',name='Simular pago aprobado').click();page.wait_for_load_state('networkidle')
    assert page.locator('.status').inner_text() in ['confirmed','Confirmada']
    page.screenshot(path=str(out/'confirmed.png'));results.append('Búsqueda → login + MFA → seguro → reserva → pago → confirmación')
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'appointment-mobile.png'))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.get_by_role('button',name='Cancelar cita y reembolsar').click();page.wait_for_url('**/panel/');results.append('Cancelación y reembolso simulado')
    page.goto('https://localhost:8443/dependents/new/');page.get_by_label('Nombre del dependiente').fill('Dependiente Sintético Navegador');page.locator('#id_age').fill('8');page.get_by_label('Código de evidencia').fill('DEMO-VINCULO-BROWSER-2026');page.get_by_role('button',name='Continuar',exact=True).click();page.wait_for_url('**/panel/');results.append('Solicitud de representación pendiente')
    ctx.close()
    for username in ['medico.a','recepcion.a','seguro.1','operador.a','operador.b']:
        ctx=context();page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));login(page,username)
        if username=='operador.a':
            row=page.locator('.list-row').filter(has_text='Pendiente de revisión independiente.').first
            row.get_by_role('checkbox').check();row.get_by_role('button',name='Validar vínculo de ensayo').click();page.wait_for_load_state('networkidle')
            assert db_call(lambda: Representation.objects.filter(name='Dependiente Sintético Navegador',verified_at__isnull=False).exists());results.append('Verificación independiente habilita representación')
        page.screenshot(path=str(out/(username.replace('.','-')+'.png')))
        results.append('Panel por rol: '+username);ctx.close()
    browser.close()
assert not errors, errors
report={'passed':True,'checks':results,'javascript_errors':errors,'viewports':['1440x1000','390x844'],'screenshots':str(out),'tls_note':'Validación TLS activa. Requiere certificado local confiable (scripts/trust_local_https.py).'}
(ROOT/'evidence/browser.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));print(json.dumps(report,indent=2,ensure_ascii=False))
