
import os

filepath = r'c:\Users\Laptop\OneDrive\Desktop\E-Commerce\store\forms.py'
with open(filepath, 'r') as f:
    content = f.read()

# 1. Redefine AddProductForm Meta
# We'll just overwrite the whole class or the Meta block to be sure.

import re

add_form_meta_pattern = re.compile(r'class AddProductForm\(forms\.ModelForm\):.*?class Meta:.*?labels = \{.*?\}', re.DOTALL)
update_form_meta_pattern = re.compile(r'class UpdateProductForm\(forms\.ModelForm\):.*?class Meta:.*?labels = \{.*?\}', re.DOTALL)

add_meta_replacement = """class AddProductForm(forms.ModelForm):
    \"\"\"Purchase + product fields for new inventory.\"\"\"

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
        }"""

update_meta_replacement = """class UpdateProductForm(forms.ModelForm):
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
        }"""

content = add_form_meta_pattern.sub(add_meta_replacement, content)
content = update_form_meta_pattern.sub(update_meta_replacement, content)

# 2. Update __init__ to include unit_capacity in required fields and handle visibility
# We'll just make all these fields always visible as requested by the simplified Add Product goal.

init_pattern = re.compile(r'def __init__\(self, \*args, store_owner=None, ad_section=False, \*\*kwargs\):.*?if self\.ad_section:.*?else:.*?Decimal\(\'0\.00\'\)\)', re.DOTALL)
init_replacement = """def __init__(self, *args, store_owner=None, ad_section=False, **kwargs):
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
        self.fields['total_amount'].required = False"""

content = init_pattern.sub(init_replacement, content)

with open(filepath, 'w') as f:
    f.write(content)
