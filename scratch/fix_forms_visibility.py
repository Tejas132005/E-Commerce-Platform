
import os

filepath = r'c:\Users\Laptop\OneDrive\Desktop\E-Commerce\store\forms.py'
with open(filepath, 'r') as f:
    content = f.read()

# Make net_amount and total_amount visible always
content = content.replace(
    "self.fields['net_amount'].widget = forms.HiddenInput()",
    "pass # was HiddenInput"
)
content = content.replace(
    "self.fields['total_amount'].widget = forms.HiddenInput()",
    "pass # was HiddenInput"
)

with open(filepath, 'w') as f:
    f.write(content)
