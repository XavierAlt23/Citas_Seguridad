from django.http import JsonResponse
from django.contrib.auth import logout
from .security import limited, audit
from .waf import inspect

class Guard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        early=None
        if not request.path.startswith('/static/'):
            early=inspect(request)
            if limited('ip:' + request.META.get('REMOTE_ADDR', ''), 300):
                early=JsonResponse({'error': 'Demasiadas solicitudes. Espera un minuto.'}, status=429)
                early['Retry-After']='60'
            if request.user.is_authenticated and not request.session.get('mfa_verified'):
                logout(request)
            if request.user.is_authenticated and not request.user.is_active:
                logout(request)
        response = early if early is not None else self.get_response(request)
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response['Cache-Control'] = 'no-store'
        if request.user.is_authenticated and response.status_code == 403:
            audit(request.user, 'request.forbidden', request.path, 'denied')
        if request.user.is_authenticated and request.method == 'GET' and response.status_code == 200 and not request.path.startswith('/static/'):
            audit(request.user, 'resource.read', request.path)
        return response
