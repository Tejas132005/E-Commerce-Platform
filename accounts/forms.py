# accounts/forms.py

from django import forms
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone', 'company_name', 'dob', 'location', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if password != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Phone")
    password = forms.CharField(widget=forms.PasswordInput())
