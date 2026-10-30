import hashlib, json, time, uuid, io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
import pyotp
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connections, connection, transaction, DatabaseError
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.utils import timezone
from .models import *
from .security import *
from .services import *
from django.core.management.base import CommandError

class Fixtures:
    def data(self):
        self.c1=Center.objects.create(name='Centro A'); self.c2=Center.objects.create(name='Centro B')
        self.i1=Insurer.objects.create(id=1,name='Seguro A',copay=1250); self.i2=Insurer.objects.create(id=2,name='Seguro B',copay=1500)
        self.a=User.objects.create_user(username='alice',password='Synthetic-long-test-pass-2026',role='patient',mfa_cipher=encrypt(pyotp.random_base32()),mfa_ready=True)
        self.b=User.objects.create_user(username='bob',password='Synthetic-long-test-pass-2026',role='patient')
        self.r=User.objects.create_user(username='reception',role='reception',center=self.c2)
        self.o=User.objects.create_user(username='operator',role='operator')
        self.ins=User.objects.create_user(username='insurer',role='insurer',insurer=self.i2)
        self.prof=Professional.objects.create(name='Doctor A',specialty='General',center=self.c1)
        self.slot=Slot.objects.create(professional=self.prof,start=timezone.now()+timedelta(days=2))
        self.policy=Policy.objects.create(owner=self.a,insurer=self.i1,reference_cipher=encrypt('DEMO-POLICY'))
    def auth(self,user,csrf=False):
        client=Client(enforce_csrf_checks=csrf); client.force_login(user)
        session=client.session; session['mfa_verified']=True; session.save(); return client
    def book(self): return reserve(self.a,self.slot.pk,uuid.uuid4(),self.policy.pk)
    def signed(self,payload,kind='psp',partner_id=1,nonce=None):
        body=json.dumps(payload).encode(); stamp=str(int(time.time())); nonce=nonce or str(uuid.uuid4())
        partner='psp' if kind=='psp' else f'insurer:{partner_id}'; scope='payments:write' if kind=='psp' else 'eligibility:check'; key=settings.PSP_KEY if kind=='psp' else settings.PARTNER_KEYS[partner_id-1]
        url='/integrations/psp/' if kind=='psp' else f'/integrations/insurers/{partner_id}/'
        headers={'HTTP_X_SCOPE':scope,'HTTP_X_TIMESTAMP':stamp,'HTTP_X_NONCE':nonce,'HTTP_X_SIGNATURE':sign(key,partner,scope,stamp,nonce,body)}
        return url,body,headers

@override_settings(SECURE_SSL_REDIRECT=False)
class SecurityTests(Fixtures,TestCase):
    def setUp(self): self.data()
    def test_P01_no_prohibited_data_schema(self):
        columns={f.name for model in [User,Appointment,Payment,Policy,Representation] for f in model._meta.fields}
        self.assertFalse(columns & {'diagnosis','religion','income','pan','cvv','history','geolocation'})
        self.assertNotEqual(self.policy.reference_cipher,'DEMO-POLICY'); self.assertEqual(decrypt(self.policy.reference_cipher),'DEMO-POLICY')
    def test_P02_insurer_cannot_read_foreign_policy(self):
        self.assertEqual(self.auth(self.ins).get(f'/api/policies/{self.policy.pk}/').status_code,403)
        self.ins.insurer=self.i1; self.ins.save()
        self.assertEqual(self.auth(self.ins).get(f'/api/policies/{self.policy.pk}/').status_code,200)
    def test_P03_unverified_dependent_rejected(self):
        d=Representation.objects.create(owner=self.a,name='Minor',age=7,evidence_digest='a'*64)
        with self.assertRaises(PermissionDenied): reserve(self.a,self.slot.pk,uuid.uuid4(),dependent_id=d.pk)
        d.verified_by=self.o; d.verified_at=timezone.now(); d.save()
        self.assertEqual(reserve(self.a,self.slot.pk,uuid.uuid4(),dependent_id=d.pk).dependent_id,d.pk)
    def test_P03_no_evidence_cannot_request_representation(self):
        response=self.auth(self.a).post('/dependents/new/',{'name':'Minor','age':7,'evidence':''})
        self.assertEqual(response.status_code,200); self.assertEqual(Representation.objects.count(),0)
    def test_P04_logout_revokes_old_cookie(self):
        client=self.auth(self.a); cookie=client.cookies[settings.SESSION_COOKIE_NAME].value
        client.post('/logout/'); client.cookies[settings.SESSION_COOKIE_NAME]=cookie
        self.assertEqual(client.get('/panel/').status_code,302)
    def test_P04_expired_session_rejected(self):
        client=self.auth(self.a)
        from django.contrib.sessions.models import Session
        Session.objects.filter(session_key=client.session.session_key).update(expire_date=timezone.now()-timedelta(seconds=1))
        self.assertEqual(client.get('/panel/').status_code,302)
    def test_P05_unsigned_and_replayed_partner_message(self):
        p={'policy':str(self.policy.pk),'beneficiary':str(self.a.pk),'service':'consultation'}
        self.assertEqual(self.client.post('/integrations/insurers/1/',json.dumps(p),content_type='application/json').status_code,403)
        url,body,headers=self.signed(p,'insurer')
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,200)
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,400)
    def test_P05_partner_tenant_and_beneficiary_checked(self):
        p={'policy':str(self.policy.pk),'beneficiary':str(self.a.pk),'service':'consultation'}
        url,body,headers=self.signed(p,'insurer',2)
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,403)
        p['beneficiary']=str(self.b.pk); url,body,headers=self.signed(p,'insurer',1)
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,403)
    def test_P06_forged_webhook_no_state_change(self):
        a=self.book(); payment=Payment.objects.get(appointment=a)
        p={'payment':str(payment.pk),'amount':payment.amount,'currency':'USD','event':str(uuid.uuid4()),'status':'paid'}
        url,body,headers=self.signed(p); headers['HTTP_X_SIGNATURE']='0'*64
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,400)
        payment.refresh_from_db(); self.assertEqual(payment.status,'pending')
    def test_P06_wrong_amount_and_currency_rejected(self):
        a=self.book(); payment=Payment.objects.get(appointment=a)
        p={'payment':str(payment.pk),'amount':1,'currency':'EUR','event':str(uuid.uuid4()),'status':'paid'}
        url,body,headers=self.signed(p)
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,400)
        a.refresh_from_db(); self.assertEqual(a.status,'pending')
    def test_P06_payment_then_cancel_refunds_once(self):
        a=self.book(); sandbox_pay(self.a,a.pk); a.refresh_from_db(); self.assertEqual(a.status,'confirmed')
        cancel(self.a,a.pk); cancel(self.a,a.pk)
        self.assertEqual(Refund.objects.count(),1); self.assertEqual(Payment.objects.get(appointment=a).status,'refunded')
    def test_P06_duplicate_event_is_idempotent_with_new_delivery_nonce(self):
        a=self.book(); payment=Payment.objects.get(appointment=a)
        p={'payment':str(payment.pk),'amount':payment.amount,'currency':'USD','event':str(uuid.uuid4()),'status':'paid'}
        for _ in range(2):
            url,body,headers=self.signed(p)
            self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,200)
        self.assertEqual(Payment.objects.filter(status='paid').count(),1); self.assertEqual(Notice.objects.count(),1)
    def test_P07_patient_and_wrong_center_denied(self):
        a=self.book()
        for user in [self.b,self.r,self.o,self.ins]:
            self.assertEqual(self.auth(user).get(f'/api/appointments/{a.pk}/').status_code,403)
        self.assertEqual(self.auth(self.a).get(f'/api/appointments/{a.pk}/').status_code,200)
    def test_P07_wrong_professional_denied(self):
        a=self.book(); doctor=User.objects.create_user(username='doctor',role='professional',center=self.c1)
        self.assertEqual(self.auth(doctor).get(f'/api/appointments/{a.pk}/').status_code,403)
        self.prof.account=doctor; self.prof.save()
        self.assertEqual(self.auth(doctor).get(f'/api/appointments/{a.pk}/').status_code,200)
        self.assertNotContains(self.auth(doctor).get(f'/appointments/{a.pk}/'),'Copago / particular')
    def test_P08_retry_key_must_match_payload(self):
        key=uuid.uuid4(); a=reserve(self.a,self.slot.pk,key)
        self.assertEqual(reserve(self.a,self.slot.pk,key).pk,a.pk)
        with self.assertRaises(ValidationError): reserve(self.a,self.slot.pk,key,self.policy.pk)
    def test_P09_bruteforce_limited_generic_errors(self):
        statuses=[self.client.post('/login/',{'username':'nonexistent','password':'wrong'}).status_code for _ in range(6)]
        self.assertEqual(statuses[-1],429); self.assertTrue(Audit.objects.filter(action='login.limited').exists())
    def test_P09_real_mfa_and_code_cannot_be_reused(self):
        client=Client(); client.post('/login/',{'username':'alice','password':'Synthetic-long-test-pass-2026'})
        self.assertEqual(client.get('/panel/').status_code,302)
        code=pyotp.TOTP(decrypt(self.a.mfa_cipher)).now()
        self.assertEqual(client.post('/mfa/',{'code':code}).status_code,302)
        cookie=client.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['secure']); self.assertTrue(cookie['httponly']); self.assertEqual(cookie['samesite'],'Strict')
        self.assertEqual(client.get('/panel/').status_code,200)
        self.assertTrue(self.a.password.startswith('argon2$'))
        client.post('/logout/'); client.post('/login/',{'username':'alice','password':'Synthetic-long-test-pass-2026'})
        self.assertContains(client.post('/mfa/',{'code':code}),'ya utilizado')
    def demo_account(self):
        return User.objects.create_user(username='paciente.a',password='Synthetic-long-test-pass-2026',role='patient',mfa_ready=True)
    def demo_challenge_login(self, client):
        response=client.post('/login/',{'username':'paciente.a','password':'Synthetic-long-test-pass-2026'})
        self.assertRedirects(response,'/mfa/')
        output=io.StringIO();call_command('demo_code','paciente.a',stdout=output)
        return output.getvalue().strip()
    def test_demo_each_login_has_new_code_and_previous_code_rejected(self):
        user=self.demo_account();client=Client()
        first=self.demo_challenge_login(client)
        self.assertEqual(client.post('/mfa/',{'code':first}).status_code,302)
        self.assertEqual(client.get('/panel/').status_code,200)
        self.assertFalse(RateBucket.objects.filter(key=fingerprint('mfa:'+str(user.pk))).exists())
        self.assertFalse(RateBucket.objects.filter(key=fingerprint('login:user:paciente.a')).exists())
        with self.assertRaises(CommandError): call_command('demo_code','paciente.a',stdout=io.StringIO())
        client.post('/logout/')
        second=self.demo_challenge_login(client)
        self.assertNotEqual(first,second)
        self.assertContains(client.post('/mfa/',{'code':first}),'otro inicio de sesión')
        self.assertEqual(client.get('/panel/').status_code,302)
        self.assertEqual(client.post('/mfa/',{'code':second}).status_code,302)
        self.assertEqual(client.get('/panel/').status_code,200)
        self.assertEqual(MFAChallenge.objects.filter(user=user,consumed_at__isnull=False).count(),2)
    def test_demo_new_password_login_revokes_previous_pending_challenge(self):
        user=self.demo_account();one=Client();two=Client()
        old=self.demo_challenge_login(one);new=self.demo_challenge_login(two)
        self.assertNotEqual(old,new)
        self.assertContains(one.post('/mfa/',{'code':old}),'otro inicio de sesión')
        self.assertContains(one.post('/mfa/',{'code':new}),'otro inicio de sesión')
        self.assertEqual(two.post('/mfa/',{'code':new}).status_code,302)
    def test_demo_expired_code_rejected(self):
        user=self.demo_account();client=Client();code=self.demo_challenge_login(client)
        MFAChallenge.objects.filter(user=user).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertContains(client.post('/mfa/',{'code':code}),'otro inicio de sesión')
        with self.assertRaises(CommandError): call_command('demo_code','paciente.a',stdout=io.StringIO())
    def test_demo_unlock_is_audited_and_does_not_allow_normal_accounts(self):
        user=self.demo_account()
        for key in ['mfa:'+str(user.pk),'login:user:paciente.a']: limited(key,1,300)
        call_command('demo_unlock','paciente.a',stdout=io.StringIO())
        self.assertFalse(RateBucket.objects.filter(key=fingerprint('mfa:'+str(user.pk))).exists())
        self.assertTrue(Audit.objects.filter(action='demo.auth_unlocked',object_id=str(user.pk)).exists())
        with self.assertRaises(CommandError): call_command('demo_unlock','alice',stdout=io.StringIO())
    def test_P10_notifications_neutral(self):
        a=self.book(); sandbox_pay(self.a,a.pk)
        self.assertEqual(Notice.objects.get().text,'Tienes una actualización. Ingresa a tu cuenta para consultarla.')
    def test_P11_individual_audit_and_protected_updates(self):
        audit(self.a,'test.one'); audit(self.b,'test.two')
        self.assertNotEqual(Audit.objects.get(action='test.one').actor,Audit.objects.get(action='test.two').actor)
        call_command('verify_audit',verbosity=0)
        with self.assertRaises(DatabaseError):
            with transaction.atomic(): Audit.objects.filter(action='test.one').update(action='tampered')
    def test_P13_SQL_does_not_change_records(self):
        before=User.objects.count()
        self.client.get('/',{'specialty':"' OR 1=1; DROP TABLE app_user; --"})
        response=self.client.get('/',{'specialty':"x' OR 'a'='a"})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'No hay horarios con estos filtros')
        self.assertEqual(User.objects.count(),before)
    def test_P13_XSS_escaped_and_CSP_set(self):
        self.a.first_name='<script>alert(1)</script>'; self.a.save()
        response=self.auth(self.a).get('/panel/')
        self.assertNotContains(response,'<script>alert(1)</script>'); self.assertContains(response,'&lt;script&gt;')
        self.assertIn("script-src 'self'",response['Content-Security-Policy']); self.assertEqual(response['X-Frame-Options'],'DENY')
    def test_P13_CSRF_and_security_cookie_flags(self):
        client=self.auth(self.a,True)
        self.assertEqual(client.post('/account/close/',{}).status_code,403)
        self.assertTrue(settings.SESSION_COOKIE_SECURE); self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
    def test_P14_retention_and_legal_hold(self):
        self.a.closed_at=timezone.now()-timedelta(days=370); self.a.is_active=False; self.a.save()
        self.b.closed_at=self.a.closed_at; self.b.is_active=False; self.b.save()
        LegalHold.objects.create(owner=self.b,reason_code='DEMO-LEGAL')
        call_command('maintenance',verbosity=0); self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual(self.a.email,''); self.assertEqual(self.a.first_name,'Disociado'); self.assertNotEqual(self.b.first_name,'Disociado')
        self.assertEqual(Erasure.objects.count(),1)
    def test_R20_reception_cannot_change_roles(self):
        self.assertEqual(self.auth(self.r).post('/roles/',{'target':self.a.pk}).status_code,403)
    def test_R20_two_operators_and_revocation_required(self):
        other=User.objects.create_user(username='operator2',role='operator')
        self.auth(self.o).post('/roles/',{'target':str(self.r.pk),'role':'insurer','insurer':self.i1.pk})
        change=RoleChange.objects.get()
        self.assertEqual(self.auth(self.o).post('/roles/',{'approve':change.pk}).status_code,403)
        self.r.refresh_from_db();self.assertEqual(self.r.role,'reception')
        oldclient=self.auth(self.r)
        self.assertEqual(self.auth(other).post('/roles/',{'approve':change.pk}).status_code,302)
        self.r.refresh_from_db();self.assertEqual(self.r.role,'insurer');self.assertEqual(self.r.insurer_id,self.i1.pk)
        self.assertEqual(oldclient.get('/panel/').status_code,302)
    def test_WAF_blocks_known_SQL_XSS_and_oversized_requests(self):
        self.assertEqual(self.client.get('/',{'specialty':"' OR 1=1"}).status_code,400)
        self.assertEqual(self.client.get('/',{'specialty':'<script>alert(1)</script>'}).status_code,400)
        self.assertEqual(self.client.post('/login/','x'*33000,content_type='text/plain').status_code,413)
    def test_expired_payment_never_confirms(self):
        a=self.book(); a.expires_at=timezone.now()-timedelta(seconds=1); a.save()
        with self.assertRaises(ValidationError): sandbox_pay(self.a,a.pk)
        call_command('maintenance',verbosity=0); a.refresh_from_db(); self.assertEqual(a.status,'expired')
    def test_scope_and_stale_timestamp_rejected(self):
        url,body,headers=self.signed({}); headers['HTTP_X_SCOPE']='admin:all'
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,403)
        headers['HTTP_X_SCOPE']='payments:write'; headers['HTTP_X_TIMESTAMP']='1'
        self.assertEqual(self.client.post(url,body,content_type='application/json',**headers).status_code,400)
    def test_reception_can_publish_only_own_center_slots(self):
        future=(timezone.localtime()+timedelta(days=5)).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(self.auth(self.r).post('/slots/new/',{'professional':self.prof.pk,'start':future}).status_code,403)
        self.r.center=self.c1;self.r.save()
        before=Slot.objects.count()
        self.assertEqual(self.auth(self.r).post('/slots/new/',{'professional':self.prof.pk,'start':future}).status_code,302)
        self.assertEqual(Slot.objects.count(),before+1)

@override_settings(SECURE_SSL_REDIRECT=False)
class ConcurrencyTests(Fixtures,TransactionTestCase):
    reset_sequences=True
    def test_P08_100_contenders_exactly_one_confirmation(self):
        self.data()
        users=[User(username=f'contender-{i}',password='!unusable',role='patient') for i in range(100)]
        User.objects.bulk_create(users); barrier=Barrier(100)
        def attempt(user):
            connections.close_all(); barrier.wait(timeout=30)
            try:
                a=reserve(user,self.slot.pk,uuid.uuid4()); sandbox_pay(user,a.pk); return 'confirmed'
            except ValidationError: return 'conflict'
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=100) as pool: results=list(pool.map(attempt,users))
        self.assertEqual(results.count('confirmed'),1); self.assertEqual(results.count('conflict'),99)
        self.assertEqual(Appointment.objects.filter(slot=self.slot,status='confirmed').count(),1)
        self.assertEqual(Payment.objects.filter(status='paid').count(),1)
        from pathlib import Path
        Path('evidence').mkdir(exist_ok=True)
        Path('evidence/concurrency.json').write_text(json.dumps({'attempts':100,'workers':100,'confirmed':1,'conflicts':99,'database':connection.vendor,'type':'real PostgreSQL transactions; synthetic users'},indent=2))
