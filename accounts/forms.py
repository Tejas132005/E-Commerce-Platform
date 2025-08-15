# accounts/forms.py

from django import forms
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'phone', 'company_name', 'dob', 'location', 
            'company_address', 'company_city', 'company_state', 'company_pincode',
            'company_phone', 'company_email', 'company_gstin', 'password'
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'company_address': forms.Textarea(attrs={'rows': 3}),
            'company_gstin': forms.TextInput(attrs={'placeholder': 'Enter 15-digit GSTIN (Optional)'}),
        }
        help_texts = {
            'company_gstin': 'GST Identification Number (Optional - Leave blank if not applicable)',
            'company_address': 'Complete business address for invoices',
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if password != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def clean_company_gstin(self):
        gstin = self.cleaned_data.get('company_gstin')
        if gstin and len(gstin) not in [0, 15]:
            raise forms.ValidationError("GSTIN must be exactly 15 characters long or leave blank.")
        return gstin


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Phone")
    password = forms.CharField(widget=forms.PasswordInput())