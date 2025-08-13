# store/forms.py

from django import forms
from .models import Product, ShopCustomer

class AddProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price', 'quantity', 'category', 'gst', 'hsn_code', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Electronics, Clothing, Food'
            }),
            'gst': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'hsn_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HSN/SAC Code'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }

class UpdateProductForm(forms.Form):
    product_name = forms.CharField(max_length=255)
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    quantity = forms.IntegerField(min_value=0)
    category = forms.CharField(max_length=100, required=False)
    gst = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False)
    hsn_code = forms.CharField(max_length=20, required=False)

class DeleteProductForm(forms.Form):
    product_name = forms.CharField(max_length=255)

class CustomerLoginForm(forms.Form):
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number',
            'pattern': '[0-9]*',
            'title': 'Please enter only numbers'
        })
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        if len(phone) < 10:
            raise forms.ValidationError('Phone number must be at least 10 digits long.')
        
        return phone

class CustomerRegisterForm(forms.ModelForm):
    class Meta:
        model = ShopCustomer
        fields = ['name', 'phone', 'email', 'place']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your full name',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your phone number',
                'pattern': '[0-9]*',
                'title': 'Please enter only numbers',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email address (optional)'
            }),
            'place': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your location/address (optional)'
            })
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        if len(phone) < 10:
            raise forms.ValidationError('Phone number must be at least 10 digits long.')
        
        return phone

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Name must be at least 2 characters long.')
        return name