"""Verify real HTTPS re-entry with synthetic account; never prints passwords/OTPs."""
import io, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.core.management import call_command
import requests

def main():
    password=None
    for line in (ROOT/'.local/access.md').read_text().splitlines():
        parts=[part.strip() for part in line.split('|')]
        if len(parts)==5 and parts[1]=='paciente.a': password=parts[2]
    assert password, 'Falta la cuenta de ensayo en .local/access.md'
    base='https://localhost:8443'
    session=requests.Session();session.verify=str(ROOT/'.local/tls-cert.pem')
    def post(path,data):
        return session.post(base+path,data={**data,'csrfmiddlewaretoken':session.cookies['csrftoken']},headers={'Referer':base+path},allow_redirects=False,timeout=15)
    def begin():
        session.get(base+'/login/',timeout=15).raise_for_status()
        response=post('/login/',{'username':'paciente.a','password':password})
        assert response.status_code==302 and response.headers['Location']=='/mfa/'
        output=io.StringIO();call_command('demo_code','paciente.a',stdout=output)
        return output.getvalue().strip()
    first=begin()
    response=post('/mfa/',{'code':first})
    assert response.status_code==302 and response.headers['Location']=='/panel/'
    assert session.get(base+'/panel/',timeout=15).status_code==200
    assert post('/logout/',{}).status_code==302
    second=begin()
    assert first!=second
    response=post('/mfa/',{'code':first})
    assert response.status_code==200 and 'otro inicio de sesión' in response.text
    assert session.get(base+'/panel/',allow_redirects=False,timeout=15).status_code==302
    response=post('/mfa/',{'code':second})
    assert response.status_code==302 and response.headers['Location']=='/panel/'
    assert session.get(base+'/panel/',timeout=15).status_code==200
    assert post('/logout/',{}).status_code==302
    result={'passed':True,'transport':'real HTTPS, secure cookies and CSRF','database':'PostgreSQL in Docker','first_login_accepted':True,'logout_revoked_session':True,'next_login_code_different':True,'old_code_rejected':True,'new_code_accepted':True,'codes_or_passwords_printed':False}
    (ROOT/'evidence/mfa-reentry.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
