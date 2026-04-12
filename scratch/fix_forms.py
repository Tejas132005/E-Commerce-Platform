
import os

filepath = r'c:\Users\Laptop\OneDrive\Desktop\E-Commerce\store\forms.py'
with open(filepath, 'r') as f:
    content = f.read()

# 1. Update AddProductForm fields
content = content.replace(
    "'measurement_type', 'unit_value', 'unit_amount', 'net_amount'",
    "'measurement_type', 'unit_value', 'net_amount', 'total_amount'"
)

# 2. Update AddProductForm labels
content = content.replace(
    "'unit_value': 'Unit value (pack size)',",
    "'unit_value': 'Taxable Unit Amount',"
)
content = content.replace(
    "'unit_amount': 'Unit Price (Purchase)',",
    "" # Remove unit_amount label
)
content = content.replace(
    "'net_amount': 'Net Amount (Purchase)',",
    "'net_amount': 'Taxable Total Amount',\n            'total_amount': 'Total Amount',"
)

# 3. Repeat for UpdateProductForm (if not already handled by general replace)
# (The replace above are specific enough)

# 4. Update unit_value widget and add total_amount widget
content = content.replace(
    """'unit_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',
                'min': '0.0001',
                'placeholder': 'e.g. 1, 500, 2',
            }),""",
    """'unit_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Price per unit',
            }),"""
)

content = content.replace(
    """'net_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Total amount',
            }),""",
    """'net_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Taxable total',
            }),
            'total_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'GST inclusive total',
            }),"""
)

# 5. Fix unit_amount removal in Meta widgets if it's there
content = content.replace(
    """'unit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Price per unit',
            }),""",
    ""
)

with open(filepath, 'w') as f:
    f.write(content)

print("Forms updated successfully")
