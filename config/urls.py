from django.urls import path
from app import views as v
urlpatterns = [
    path('', v.home, name='home'), path('login/', v.sign_in, name='login'), path('register/', v.register, name='register'), path('mfa/', v.mfa, name='mfa'), path('mfa/qr/', v.mfa_qr, name='mfa_qr'), path('logout/', v.sign_out, name='logout'),
    path('panel/', v.dashboard, name='dashboard'), path('reserve/<int:slot_id>/', v.booking, name='booking'), path('appointments/<uuid:pk>/', v.appointment, name='appointment'), path('appointments/<uuid:pk>/pay/', v.pay, name='pay'), path('appointments/<uuid:pk>/cancel/', v.cancel_view, name='cancel'),
    path('slots/new/',v.add_slot,name='add_slot'),
    path('policies/new/', v.policy_add, name='policy_add'), path('dependents/new/', v.dependent_add, name='dependent_add'), path('dependents/<uuid:pk>/verify/', v.verify_dependent, name='verify_dependent'), path('roles/', v.roles, name='roles'), path('account/close/', v.close_account, name='close_account'), path('account/export/', v.export_data, name='export'), path('privacy/', v.privacy, name='privacy'),
    path('api/appointments/<uuid:pk>/', v.api_appointment), path('api/policies/<uuid:pk>/', v.api_policy), path('integrations/psp/', v.integration, {'kind': 'psp'}), path('integrations/insurers/<int:partner_id>/', v.integration, {'kind': 'insurer'}), path('sw.js', v.service_worker),
]
