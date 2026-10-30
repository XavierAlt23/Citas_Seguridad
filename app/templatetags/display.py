from django import template
register=template.Library()
@register.filter
def dollars(cents):
    return f'{int(cents)/100:.2f}'

@register.filter
def state(value):
    return {'pending':'Pendiente','confirmed':'Confirmada','cancelled':'Cancelada','expired':'Expirada','paid':'Pagado','denied':'Denegado','refunded':'Reembolsado'}.get(value,value)
