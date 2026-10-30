import io, json, time, uuid, secrets, hmac
import pyotp, qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from .forms import LoginForm, RegisterForm, DependentForm
from .models import *
from .security import *
from .services import *
from .demo_auth import uses_login_challenge, create_login_challenge

ROLE_LABELS = {'patient': 'Paciente', 'professional': 'Profesional', 'reception': 'Recepción', 'insurer': 'Aseguradora', 'operator': 'Operación'}

def numeric_id(value):
    value=str(value or '')
    return int(value) if value.isascii() and value.isdecimal() and len(value)<=9 else 0

def home(request):
    slots = Slot.objects.select_related('professional__center').filter(start__gt=timezone.now()).exclude(appointment__status='confirmed').exclude(appointment__status='pending', appointment__expires_at__gt=timezone.now())
    if request.GET.get('specialty'): slots = slots.filter(professional__specialty=request.GET['specialty'][:80])
    if request.GET.get('center'): slots = slots.filter(professional__center_id=numeric_id(request.GET['center']))
    if request.GET.get('date'):
        try:
            from datetime import date
            slots = slots.filter(start__date=date.fromisoformat(request.GET['date']))
        except ValueError: messages.error(request, 'La fecha no es válida.')
    return render(request, 'home.html', {'slots': slots.order_by('start', 'professional__name')[:60], 'specialties': Professional.objects.values_list('specialty', flat=True).distinct().order_by('specialty'), 'centers': Center.objects.all(), 'insurers': Insurer.objects.all()})

def sign_in(request):
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['username'].lower()
        if limited('login:user:' + name, 5, 300) or limited('login:ip:' + request.META.get('REMOTE_ADDR', ''), 15, 300):
            audit('anonymous', 'login.limited', fingerprint(name), 'blocked')
            return render(request, 'form.html', {'form': form, 'title': 'Iniciar sesión', 'error': 'Demasiados intentos. Espera cinco minutos.'}, status=429)
        user = authenticate(request, username=name, password=form.cleaned_data['password'])
        if user:
            request.session.flush()
            request.session['preauth'] = str(user.pk)
            request.session['preauth_until'] = int(time.time()) + 300
            if uses_login_challenge(user):
                binding = secrets.token_urlsafe(32)
                challenge = create_login_challenge(user, binding)
                request.session['preauth_binding'] = binding
                request.session['preauth_challenge'] = str(challenge.pk)
            if not user.mfa_cipher:
                user.mfa_cipher = encrypt(pyotp.random_base32()); user.save(update_fields=['mfa_cipher'])
            return redirect('mfa')
        audit('anonymous', 'login.failed', fingerprint(name), 'denied')
        form.add_error(None, 'Credenciales inválidas.')
    return render(request, 'form.html', {'form': form, 'title': 'Iniciar sesión', 'intro': 'Tu cuenta se protege con contraseña y un segundo factor.'})

def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if limited('register:' + request.META.get('REMOTE_ADDR', ''), 5, 3600): return HttpResponse('Espera antes de crear otra cuenta.', status=429)
        user = User.objects.create_user(username=form.cleaned_data['username'], password=form.cleaned_data['password'], first_name=form.cleaned_data['first_name'], email=form.cleaned_data['email'], role='patient')
        audit(user, 'account.created')
        messages.success(request, 'Cuenta creada. Inicia sesión para configurar tu segundo factor.')
        return redirect('login')
    return render(request, 'form.html', {'form': form, 'title': 'Crear mi cuenta', 'intro': 'Solo pedimos los datos necesarios para contactarte. No solicitamos historia clínica.'})

def preauth_user(request):
    if request.session.get('preauth_until', 0) < time.time(): return None
    return User.objects.filter(pk=request.session.get('preauth'), is_active=True).first() if request.session.get('preauth') else None

def mfa(request):
    user = preauth_user(request)
    if not user: return redirect('login')
    error = ''
    if request.method == 'POST':
        if limited('mfa:' + str(user.pk), 5, 300): return HttpResponse('Demasiados códigos. Espera cinco minutos.', status=429)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            verification_time = timezone.now()
            valid = False
            if uses_login_challenge(user):
                challenge = MFAChallenge.objects.select_for_update().filter(pk=request.session.get('preauth_challenge'), user=user, consumed_at=None, revoked_at=None, expires_at__gt=verification_time).first()
                if challenge and hmac.compare_digest(challenge.binding_digest, fingerprint(request.session.get('preauth_binding', ''))) and hmac.compare_digest(challenge.code_digest, fingerprint('login-code:' + request.POST.get('code', ''))):
                    challenge.consumed_at = verification_time
                    challenge.code_cipher = ''
                    challenge.save(update_fields=['consumed_at', 'code_cipher'])
                    valid = True
            else:
                totp = pyotp.TOTP(decrypt(user.mfa_cipher))
                counter = totp.timecode(verification_time)
                valid = totp.verify(request.POST.get('code', ''), for_time=verification_time) and counter > user.mfa_last
                if valid: user.mfa_last = counter
            if valid:
                user.mfa_ready = True; user.save(update_fields=['mfa_last', 'mfa_ready'])
                RateBucket.objects.filter(key__in=[fingerprint('mfa:' + str(user.pk)), fingerprint('login:user:' + user.username)]).delete()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                request.session.pop('preauth', None); request.session.pop('preauth_until', None)
                request.session.pop('preauth_binding', None); request.session.pop('preauth_challenge', None)
                request.session['mfa_verified'] = True
                request.session.set_expiry(1800)
                audit(user, 'login.success')
                return redirect('dashboard')
        audit(user, 'mfa.failed', result='denied')
        error = 'Código incorrecto, ya utilizado o perteneciente a otro inicio de sesión. Usa el código de este acceso.' if uses_login_challenge(user) else 'Código incorrecto o ya utilizado. Usa el código del intervalo actual.'
    return render(request, 'mfa.html', {'enroll': not user.mfa_ready and not uses_login_challenge(user), 'challenge_mode': uses_login_challenge(user), 'error': error})

@require_GET
def mfa_qr(request):
    user = preauth_user(request)
    if not user or user.mfa_ready: raise PermissionDenied()
    uri = pyotp.TOTP(decrypt(user.mfa_cipher)).provisioning_uri(user.username, issuer_name='Consulta Clara · Local')
    buf = io.BytesIO(); qrcode.make(uri).save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')

@require_POST
@login_required
def sign_out(request):
    MFAChallenge.objects.filter(user=request.user, consumed_at=None, revoked_at=None).update(revoked_at=timezone.now(), code_cipher='')
    audit(request.user, 'session.revoked')
    logout(request)
    return redirect('home')

@login_required
def dashboard(request):
    user = request.user
    ctx = {'role_label': ROLE_LABELS[user.role], 'appointments': visible_appointments(user).order_by('slot__start')[:100]}
    if user.role in ['professional','reception']:
        ctx['professionals']=Professional.objects.filter(account=user) if user.role=='professional' else Professional.objects.filter(center_id=user.center_id)
    if user.role == 'patient':
        ctx.update(policies=Policy.objects.filter(owner=user), dependents=Representation.objects.filter(owner=user, active=True), notices=Notice.objects.filter(owner=user).order_by('-id')[:10])
    if user.role == 'insurer':
        ctx['coverages'] = Coverage.objects.filter(policy__insurer_id=user.insurer_id).select_related('policy')[:100]
        ctx['insurer_name'] = user.insurer.name
    if user.role == 'operator':
        ctx.update(events=Audit.objects.order_by('-id')[:80], pending_links=Representation.objects.filter(verified_at=None, active=True).select_related('owner'), changes=RoleChange.objects.filter(approved_by=None).select_related('target', 'requested_by'), staff=User.objects.exclude(role='patient'), centers=Center.objects.all(), insurers=Insurer.objects.all(), metrics={'Cuentas': User.objects.count(), 'Centros': Center.objects.count(), 'Profesionales': Professional.objects.count(), 'Citas confirmadas': Appointment.objects.filter(status='confirmed').count()}, alerts=Audit.objects.filter(result__in=['blocked', 'denied', 'rejected']).order_by('-id')[:10])
    return render(request, 'dashboard.html', ctx)

@login_required
def booking(request, slot_id):
    if request.user.role != 'patient': raise PermissionDenied()
    slot = get_object_or_404(Slot.objects.select_related('professional__center'), pk=slot_id)
    if request.method == 'POST':
        try:
            appointment = reserve(request.user, slot_id, request.POST.get('key'), request.POST.get('policy') or None, request.POST.get('dependent') or None)
            return redirect('appointment', pk=appointment.pk)
        except (ValidationError, Slot.DoesNotExist) as exc: messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Horario inexistente.')
    return render(request, 'booking.html', {'slot': slot, 'policies': Policy.objects.filter(owner=request.user, active=True).select_related('insurer'), 'dependents': Representation.objects.filter(owner=request.user, active=True, verified_at__isnull=False), 'key': str(uuid.uuid4())})

@login_required
def appointment(request, pk):
    item = owned(request.user, visible_appointments(request.user), pk)
    payment = Payment.objects.get(appointment=item) if request.user.role in ['patient', 'reception'] else None
    return render(request, 'appointment.html', {'item': item, 'payment': payment, 'can_cancel': request.user.role in ['patient', 'reception']})

@require_POST
@login_required
def pay(request, pk):
    if request.user.role != 'patient': raise PermissionDenied()
    try:
        sandbox_pay(request.user, pk, request.POST.get('outcome') == 'approve')
        messages.success(request, 'La pasarela simulada procesó la operación.')
    except ValidationError as exc: messages.error(request, '; '.join(exc.messages))
    return redirect('appointment', pk=pk)

@require_POST
@login_required
def cancel_view(request, pk):
    cancel(request.user, pk)
    messages.success(request, 'Cita cancelada. Si había un pago, se generó un reembolso simulado.')
    return redirect('dashboard')

@login_required
def policy_add(request):
    if request.user.role != 'patient': raise PermissionDenied()
    error = ''
    if request.method == 'POST':
        ref = request.POST.get('reference', '')
        insurer = Insurer.objects.filter(pk=numeric_id(request.POST.get('insurer'))).first()
        if not insurer or not ref.startswith('DEMO-') or not 8 <= len(ref) <= 64: error = 'Selecciona una aseguradora y una póliza sintética DEMO- de 8 a 64 caracteres.'
        else:
            item = Policy.objects.create(owner=request.user, insurer=insurer, reference_cipher=encrypt(ref))
            audit(request.user, 'policy.created', item.id)
            messages.success(request, 'Póliza sintética vinculada. Su referencia se guarda cifrada.')
            return redirect('dashboard')
    return render(request, 'policy.html', {'insurers': Insurer.objects.all(), 'error': error})

@login_required
def dependent_add(request):
    if request.user.role != 'patient': raise PermissionDenied()
    form = DependentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False); item.owner = request.user; item.evidence_digest = fingerprint(form.cleaned_data['evidence']); item.save()
        audit(request.user, 'representation.requested', item.id)
        messages.success(request, 'Vínculo pendiente. Un operador distinto verificará la evidencia sintética antes de habilitar reservas.')
        return redirect('dashboard')
    return render(request, 'form.html', {'form': form, 'title': 'Solicitar representación', 'intro': 'Demostración con evidencia ficticia. Una cédula por sí sola no autoriza a representar a un menor.'})

@require_POST
@login_required
def verify_dependent(request, pk):
    if request.user.role != 'operator': raise PermissionDenied()
    with transaction.atomic():
        item = get_object_or_404(Representation.objects.select_for_update(), pk=pk, active=True)
        if item.owner_id == request.user.id or not item.evidence_digest or request.POST.get('reviewed') != 'yes': raise PermissionDenied()
        item.verified_by = request.user; item.verified_at = timezone.now(); item.save()
        audit(request.user, 'representation.verified', item.pk)
    messages.success(request, 'Representación verificada para la simulación académica.')
    return redirect('dashboard')

@require_POST
@login_required
def roles(request):
    if request.user.role != 'operator': raise PermissionDenied()
    if request.POST.get('approve'):
        with transaction.atomic():
            change = get_object_or_404(RoleChange.objects.select_for_update(), pk=numeric_id(request.POST['approve']), approved_by=None)
            if change.requested_by_id == request.user.id: raise PermissionDenied('Se requieren dos operadores distintos.')
            target = User.objects.select_for_update().get(pk=change.target_id)
            if target.role == 'patient' or change.proposed_role not in ['operator','reception','insurer']: raise PermissionDenied()
            target.role=change.proposed_role; target.center=change.center; target.insurer=change.insurer; target.save(update_fields=['role','center','insurer'])
            Professional.objects.filter(account=target).update(account=None)
            from django.contrib.sessions.models import Session
            for session in Session.objects.filter(expire_date__gt=timezone.now()):
                if session.get_decoded().get('_auth_user_id') == str(target.pk): session.delete()
            change.approved_by = request.user; change.save(); audit(request.user, 'role.approved', change.target_id)
    else:
        try: target_id=uuid.UUID(request.POST.get('target',''))
        except (ValueError,TypeError,AttributeError): return JsonResponse({'error':'Cuenta inválida.'},status=400)
        target = get_object_or_404(User.objects.exclude(role='patient'), pk=target_id)
        role=request.POST.get('role','operator')
        if role not in ['operator','reception','insurer']: raise PermissionDenied()
        center=None; insurer=None
        if role=='reception': center=get_object_or_404(Center,pk=numeric_id(request.POST.get('center')))
        if role=='insurer': insurer=get_object_or_404(Insurer,pk=numeric_id(request.POST.get('insurer')))
        RoleChange.objects.create(target=target, proposed_role=role, center=center, insurer=insurer, requested_by=request.user)
        audit(request.user, 'role.review_requested', target.pk)
    return redirect('dashboard')

@require_POST
@login_required
def close_account(request):
    if request.user.role != 'patient': raise PermissionDenied()
    if Appointment.objects.filter(owner=request.user, status__in=['pending', 'confirmed']).exists():
        messages.error(request, 'Cancela tus citas activas antes de cerrar la cuenta.'); return redirect('dashboard')
    user = request.user; user.closed_at = timezone.now(); user.is_active = False; user.save()
    audit(user, 'account.closed'); logout(request)
    return redirect('home')

@login_required
def export_data(request):
    if request.user.role != 'patient': raise PermissionDenied()
    audit(request.user, 'data.exported')
    return JsonResponse({'account': {'name': request.user.first_name, 'email': request.user.email}, 'appointments': list(Appointment.objects.filter(owner=request.user).values('id', 'slot_id', 'status')), 'policies': list(Policy.objects.filter(owner=request.user).values('id', 'insurer_id', 'active')), 'dependents': list(Representation.objects.filter(owner=request.user).values('name', 'age', 'verified_at'))})

def privacy(request): return render(request, 'privacy.html')

@csrf_exempt
@require_POST
def integration(request, kind, partner_id=0):
    if len(request.body) > 8192: return JsonResponse({'error': 'Mensaje demasiado grande.'}, status=413)
    partner = 'psp' if kind == 'psp' else f'insurer:{partner_id}'
    scope = 'payments:write' if kind == 'psp' else 'eligibility:check'
    if kind != 'psp' and partner_id not in range(1, 6): raise PermissionDenied()
    if request.headers.get('X-Scope') != scope: return JsonResponse({'error': 'Scope inválido.'}, status=403)
    key = settings.PSP_KEY if kind == 'psp' else settings.PARTNER_KEYS[partner_id - 1]
    try:
        verify_message(partner, scope, request.headers.get('X-Timestamp'), request.headers.get('X-Nonce', ''), request.body, request.headers.get('X-Signature', ''), key)
        payload = json.loads(request.body)
        if not isinstance(payload, dict): raise ValueError()
        result = apply_payment(payload) if kind == 'psp' else partner_coverage(partner_id, payload)
        return JsonResponse({'status': result.status} if kind == 'psp' else result)
    except (IntegrationError, ValidationError, ValueError, TypeError, IntegrityError):
        audit(partner, 'integration.invalid', result='rejected')
        return JsonResponse({'error': 'Mensaje inválido, repetido o no autorizado.'}, status=400)

@login_required
def api_appointment(request, pk):
    item = owned(request.user, visible_appointments(request.user), pk)
    return JsonResponse({'id': str(item.pk), 'status': item.status, 'slot': item.slot_id})

@login_required
def api_policy(request, pk):
    qs = Policy.objects.filter(owner=request.user) if request.user.role == 'patient' else Policy.objects.filter(insurer_id=request.user.insurer_id) if request.user.role == 'insurer' else Policy.objects.none()
    item = owned(request.user, qs, pk)
    return JsonResponse({'id': str(item.pk), 'insurer': item.insurer_id, 'active': item.active})

def service_worker(request):
    return HttpResponse("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));", content_type='application/javascript')

@require_POST
@login_required
def add_slot(request):
    user=request.user
    if user.role not in ['professional','reception']: raise PermissionDenied()
    qs=Professional.objects.filter(account=user) if user.role=='professional' else Professional.objects.filter(center_id=user.center_id)
    prof=owned(user,qs,numeric_id(request.POST.get('professional')))
    from django.utils.dateparse import parse_datetime
    try:
        start=parse_datetime(request.POST.get('start',''))
        if start and timezone.is_naive(start): start=timezone.make_aware(start)
        if not start or start<=timezone.now(): raise ValueError()
        slot,created=Slot.objects.get_or_create(professional=prof,start=start)
        audit(user,'slot.created' if created else 'slot.already_exists',slot.pk)
        messages.success(request,'Horario publicado; ya puede encontrarse en la búsqueda.')
    except (ValueError,TypeError): messages.error(request,'Selecciona una fecha y hora futuras válidas.')
    return redirect('dashboard')
