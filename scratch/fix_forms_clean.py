
import os

filepath = r'c:\Users\Laptop\OneDrive\Desktop\E-Commerce\store\forms.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
skip_until = None

for i, line in enumerate(lines):
    if skip_until and i < skip_until:
        continue
    
    # Replace unit_amount with unit_value in calculation check
    if 'unit_amt = cleaned.get(\'unit_amount\')' in line:
        new_lines.append(line.replace('unit_amount', 'unit_value'))
        continue
    
    if 'expected = (Decimal(str(unit_amt)) * int(qty))' in line:
        new_lines.append(line)
        continue

    # Remove clean_unit_amount if it exists (since unit_amount is gone from fields)
    if 'def clean_unit_amount(self):' in line:
        # skip next few lines until the next method
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith('def '):
            j += 1
        skip_until = j
        continue
    
    new_lines.append(line)

content = "".join(new_lines)

# One more general replace for any remaining unit_amount in calculations
content = content.replace("unit_amt = cleaned.get('unit_amount')", "unit_amt = cleaned.get('unit_value')")

# Add total_amount cleaning if needed, but the model field handles it.
# Ensure total_amount is in the Meta fields for UpdateProductForm too (handled by previous script?)
# Actually my previous script was a bit rough. Let's do a more thorough check.

with open(filepath, 'w') as f:
    f.write(content)
