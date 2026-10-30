"""Small, explicit application firewall. Supplemental to validation and authorization."""
import re
from django.http import JsonResponse
from .security import audit

PATTERNS = re.compile(r'<\s*script\b|\bon(?:error|load)\s*=|javascript\s*:|\bunion\s+(?:all\s+)?select\b|\b(?:drop|truncate)\s+table\b|(?:\x27|\x22)\s*or\s+\d+\s*=\s*\d+|(?:\.\./){2,}|/etc/passwd|/proc/self', re.I)

def inspect(request):
    if request.method not in ['GET','HEAD','POST','OPTIONS']:
        return JsonResponse({'error':'Método no permitido.'},status=405)
    try: length=int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError: return JsonResponse({'error':'Longitud inválida.'},status=400)
    if length>32768: return JsonResponse({'error':'Solicitud demasiado grande.'},status=413)
    values=[request.path,*[value for key in request.GET for value in request.GET.getlist(key)]]
    if request.content_type=='application/x-www-form-urlencoded':
        values += [value for key in request.POST if key not in ['password','code','csrfmiddlewaretoken'] for value in request.POST.getlist(key)]
    if any(PATTERNS.search(value) for value in values):
        audit(request.user.pk if request.user.is_authenticated else 'anonymous','waf.blocked',request.path,'blocked')
        return JsonResponse({'error':'Entrada bloqueada por el filtro de seguridad.'},status=400)
    return None
