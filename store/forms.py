# store/forms.py

import re
from datetime import date
from decimal import Decimal

from django import forms
from .models import Product, ShopCustomer

GSTIN_OPTIONAL_RE = re.compile(r'^[0-9]{2}[A-Z0-9]{13}$')


class AddProductForm(forms.ModelForm):
    """Purchase + product fields for new inventory."""

    class Meta:
        model = Product
        fields = [
            'purchased_from', 'company_gstin', 'purchase_date', 'purchase_invoice_number',
            'name', 'category', 'gst', 'hsn_code', 'batch_number', 'image', 'quantity',
            'measurement_type', 'unit_capacity', 'taxable_unit_amount', 'taxable_total_amount', 'total_amount'
        ]
        widgets = {
            'purchased_from': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier name'}),
            'company_gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '15-char GSTIN', 'maxlength': '15'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_invoice_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Invoice number'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category'}),
            'gst': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'hsn_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HSN code'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Batch number'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'measurement_type': forms.Select(attrs={'class': 'form-select'}),
            'unit_capacity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 50, 2'}),
            'taxable_unit_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Price per unit'}),
            'taxable_total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Auto or manual'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Auto or manual'}),
        }
        labels = {
            'purchased_from': 'Company name (purchased from)',
            'company_gstin': 'Company GSTIN',
            'purchase_date': 'Purchase date',
            'purchase_invoice_number': 'Purchase invoice number',
            'name': 'Product name',
            'category': 'Category',
            'gst': 'GST (%)',
            'hsn_code': 'HSN',
            'batch_number': 'Batch no.',
            'image': 'Image',
            'quantity': 'Quantity (total number)',
            'measurement_type': 'Measurement type',
            'unit_capacity': 'Unit Capacity (weight/volume)',
            'taxable_unit_amount': 'Taxable Unit Amount',
            'taxable_total_amount': 'Taxable Total Amount',
            'total_amount': 'Total Amount',
        }

    def __init__(self, *args, store_owner=None, ad_section=False, **kwargs):
        self.store_owner = store_owner
        self.ad_section = bool(ad_section)
        super().__init__(*args, **kwargs)
        required_fields = (
            'purchased_from', 'purchase_date', 'purchase_invoice_number',
            'name', 'category', 'gst', 'hsn_code', 'batch_number', 'quantity', 'measurement_type',
            'unit_capacity', 'taxable_unit_amount'
        )
        for fname in required_fields:
            if fname in self.fields:
                self.fields[fname].required = True
        
        self.fields['company_gstin'].required = False
        self.fields['image'].required = False
        self.fields['taxable_total_amount'].required = False
        self.fields['total_amount'].required = False
        self.initial.setdefault('total_amount', Decimal('0.00'))
        if not self.initial.get('purchase_date') and not self.data:
            self.initial['purchase_date'] = date.today()

    def clean_purchased_from(self):
        v = (self.cleaned_data.get('purchased_from') or '').strip()
        if len(v) < 2:
            raise forms.ValidationError('Company name must be at least 2 characters.')
        return v

    def clean_company_gstin(self):
        v = (self.cleaned_data.get('company_gstin') or '').strip().upper()
        if not v:
            return ''
        if len(v) != 15:
            raise forms.ValidationError('GSTIN must be exactly 15 characters if provided.')
        if not GSTIN_OPTIONAL_RE.match(v):
            raise forms.ValidationError('Invalid GSTIN format.')
        return v

    def clean_purchase_invoice_number(self):
        v = (self.cleaned_data.get('purchase_invoice_number') or '').strip()
        if not v:
            raise forms.ValidationError('Purchase invoice number is required.')
        return v

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < 2:
            raise forms.ValidationError('Product name must be at least 2 characters.')
        return name

    def clean_category(self):
        category = (self.cleaned_data.get('category') or '').strip()
        if not category:
            raise forms.ValidationError('Category is required.')
        return category

    def clean_hsn_code(self):
        hsn = (self.cleaned_data.get('hsn_code') or '').strip()
        if not hsn:
            raise forms.ValidationError('HSN is required.')
        return hsn

    def clean_batch_number(self):
        batch = (self.cleaned_data.get('batch_number') or '').strip()
        if not batch:
            raise forms.ValidationError('Batch number is required.')
        return batch

    def clean_gst(self):
        gst = self.cleaned_data.get('gst')
        if gst is None:
            raise forms.ValidationError('GST is required.')
        g = Decimal(str(gst))
        if g < 0 or g > 100:
            raise forms.ValidationError('GST must be between 0 and 100.')
        return gst

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None:
            raise forms.ValidationError('Quantity is required.')
        if qty < 0:
            raise forms.ValidationError('Quantity cannot be negative.')
        return qty

    def clean_unit_value(self):
        uv = self.cleaned_data.get('unit_value')
        if uv is None:
            raise forms.ValidationError('Unit value is required.')
        u = Decimal(str(uv))
        if u <= 0:
            raise forms.ValidationError('Unit value must be greater than zero.')
        return uv

    def clean_net_amount(self):
        v = self.cleaned_data.get('net_amount')
        if v in (None, ''):
            if self.ad_section:
                raise forms.ValidationError('Net amount is required in AD mode.')
            return Decimal('0.00')
        d = Decimal(str(v))
        if d < 0:
            raise forms.ValidationError('Net amount cannot be negative.')
        return d

    def clean(self):
        cleaned = super().clean()
        if self.ad_section:
            q = getattr(self, 'data', None) or {}
            manual = (q.get('net_manual_override') or '').strip() == '1'
            qty = cleaned.get('quantity')
            unit_amt = cleaned.get('unit_value')
            net_amt = cleaned.get('net_amount')
            if not manual and qty is not None and unit_amt is not None and net_amt is not None:
                expected = (Decimal(str(unit_amt)) * int(qty)).quantize(Decimal('0.01'))
                if Decimal(str(net_amt)).quantize(Decimal('0.01')) != expected:
                    self.add_error(
                        'net_amount',
                        'Net amount must equal Unit amount x Quantity, or check "Manual override".',
                    )
        return cleaned


class UpdateProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'purchased_from', 'company_gstin', 'purchase_date', 'purchase_invoice_number',
            'name', 'category', 'gst', 'hsn_code', 'batch_number', 'image', 'quantity',
            'measurement_type', 'unit_capacity', 'taxable_unit_amount', 'taxable_total_amount', 'total_amount'
        ]
        widgets = {
            'purchased_from': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier name'}),
            'company_gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '15-char GSTIN', 'maxlength': '15'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_invoice_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Invoice number'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category'}),
            'gst': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'hsn_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HSN code'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Batch number'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'measurement_type': forms.Select(attrs={'class': 'form-select'}),
            'unit_capacity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 50, 2'}),
            'taxable_unit_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Price per unit'}),
            'taxable_total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Auto or manual'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Auto or manual'}),
        }
        labels = {
            'purchased_from': 'Company name (purchased from)',
            'company_gstin': 'Company GSTIN',
            'purchase_date': 'Purchase date',
            'purchase_invoice_number': 'Purchase invoice number',
            'name': 'Product name',
            'category': 'Category',
            'gst': 'GST (%)',
            'hsn_code': 'HSN',
            'batch_number': 'Batch no.',
            'image': 'Image',
            'quantity': 'Quantity (total number)',
            'measurement_type': 'Measurement type',
            'unit_capacity': 'Unit Capacity (weight/volume)',
            'taxable_unit_amount': 'Taxable Unit Amount',
            'taxable_total_amount': 'Taxable Total Amount',
            'total_amount': 'Total Amount',
        }

    def __init__(self, *args, store_owner=None, ad_section=False, **kwargs):
        self.store_owner = store_owner
        self.ad_section = bool(ad_section)
        super().__init__(*args, **kwargs)
        required_fields = (
            'purchased_from', 'purchase_date', 'purchase_invoice_number',
            'name', 'category', 'gst', 'hsn_code', 'batch_number', 'quantity', 'measurement_type',
            'unit_value',
        )
        for fname in required_fields:
            self.fields[fname].required = True
        self.fields['company_gstin'].required = False
        self.fields['image'].required = False
        if self.ad_section:
            self.fields['net_amount'].required = True
            self.fields['total_amount'].required = True
        else:
            self.fields['net_amount'].required = False
            self.fields['total_amount'].required = False
            pass # was HiddenInput
            pass # was HiddenInput

    def clean_purchased_from(self):
        v = (self.cleaned_data.get('purchased_from') or '').strip()
        if len(v) < 2:
            raise forms.ValidationError('Company name must be at least 2 characters.')
        return v

    def clean_company_gstin(self):
        v = (self.cleaned_data.get('company_gstin') or '').strip().upper()
        if not v:
            return ''
        if len(v) != 15:
            raise forms.ValidationError('GSTIN must be exactly 15 characters if provided.')
        if not GSTIN_OPTIONAL_RE.match(v):
            raise forms.ValidationError('Invalid GSTIN format.')
        return v

    def clean_purchase_invoice_number(self):
        v = (self.cleaned_data.get('purchase_invoice_number') or '').strip()
        if not v:
            raise forms.ValidationError('Purchase invoice number is required.')
        return v

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if len(name) < 2:
            raise forms.ValidationError('Product name must be at least 2 characters.')
        return name

    def clean_category(self):
        category = (self.cleaned_data.get('category') or '').strip()
        if not category:
            raise forms.ValidationError('Category is required.')
        return category

    def clean_hsn_code(self):
        hsn = (self.cleaned_data.get('hsn_code') or '').strip()
        if not hsn:
            raise forms.ValidationError('HSN is required.')
        return hsn

    def clean_batch_number(self):
        batch = (self.cleaned_data.get('batch_number') or '').strip()
        if not batch:
            raise forms.ValidationError('Batch number is required.')
        return batch

    def clean_gst(self):
        gst = self.cleaned_data.get('gst')
        if gst is None:
            raise forms.ValidationError('GST is required.')
        g = Decimal(str(gst))
        if g < 0 or g > 100:
            raise forms.ValidationError('GST must be between 0 and 100.')
        return gst

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None:
            raise forms.ValidationError('Quantity is required.')
        if qty < 0:
            raise forms.ValidationError('Quantity cannot be negative.')
        return qty

    def clean_unit_value(self):
        uv = self.cleaned_data.get('unit_value')
        if uv is None:
            raise forms.ValidationError('Unit value is required.')
        u = Decimal(str(uv))
        if u <= 0:
            raise forms.ValidationError('Unit value must be greater than zero.')
        return uv

    def clean_net_amount(self):
        v = self.cleaned_data.get('net_amount')
        if v in (None, ''):
            if self.ad_section:
                raise forms.ValidationError('Net amount is required in AD mode.')
            return Decimal('0.00')
        d = Decimal(str(v))
        if d < 0:
            raise forms.ValidationError('Net amount cannot be negative.')
        return d

    def clean(self):
        cleaned = super().clean()
        if self.ad_section:
            q = getattr(self, 'data', None) or {}
            manual = (q.get('net_manual_override') or '').strip() == '1'
            qty = cleaned.get('quantity')
            unit_amt = cleaned.get('unit_value')
            net_amt = cleaned.get('net_amount')
            if not manual and qty is not None and unit_amt is not None and net_amt is not None:
                expected = (Decimal(str(unit_amt)) * int(qty)).quantize(Decimal('0.01'))
                if Decimal(str(net_amt)).quantize(Decimal('0.01')) != expected:
                    self.add_error(
                        'net_amount',
                        'Net amount must equal Unit amount x Quantity, or check "Manual override".',
                    )
        return cleaned


class DeleteProductForm(forms.Form):
    product_name = forms.CharField(max_length=255)


class CustomerLoginForm(forms.Form):
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number',
            'pattern': '[0-9]*',
            'title': 'Please enter only numbers',
        }),
    )


class CustomerRegisterForm(forms.ModelForm):
    class Meta:
        model = ShopCustomer
        fields = ['name', 'phone', 'email', 'place']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number',
                'pattern': '[0-9]*',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email (optional)',
            }),
            'place': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City / location',
            }),
        }
