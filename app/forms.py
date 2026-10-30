from django import forms
from django.contrib.auth import password_validation
from .models import User, Representation

class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'username'}))
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

class RegisterForm(forms.Form):
    username = forms.RegexField(regex=r'^[a-zA-Z0-9_.-]{3,40}$', label='Usuario', max_length=40)
    first_name = forms.CharField(label='Nombre', max_length=80)
    email = forms.EmailField(label='Correo de contacto')
    password = forms.CharField(label='Contraseña (mínimo 12 caracteres)', widget=forms.PasswordInput)
    notice = forms.BooleanField(label='He leído el aviso de privacidad para gestionar mi cuenta y mis reservas.')
    def clean_username(self):
        value = self.cleaned_data['username'].lower()
        if User.objects.filter(username=value).exists(): raise forms.ValidationError('Ese usuario no está disponible.')
        return value
    def clean(self):
        data = super().clean()
        if data.get('password'):
            password_validation.validate_password(data['password'], User(username=data.get('username', ''), email=data.get('email', '')))
        return data

class DependentForm(forms.ModelForm):
    evidence = forms.CharField(label='Código de evidencia sintética (DEMO-VINCULO-…)', min_length=16, max_length=100)
    class Meta:
        model = Representation
        fields = ['name', 'age']
        labels = {'name': 'Nombre del dependiente (ficticio)', 'age': 'Edad'}
    def clean_evidence(self):
        value = self.cleaned_data['evidence']
        if not value.startswith('DEMO-VINCULO-'): raise forms.ValidationError('Usa una evidencia sintética con prefijo DEMO-VINCULO-.')
        return value
