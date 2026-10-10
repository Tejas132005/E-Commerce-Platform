# store/fy_reports.py
#
# Financial-year (1 April - 31 March) purchase, sales and inventory reporting.
# READ-ONLY: nothing in this module writes to the database, so running any
# report any number of times can never change stock, invoices or totals.
#
# Data model facts this module relies on (see store/models.py):
#   * Every Product row is ONE purchase lot: purchase_date, supplier invoice,
#     initial_stock (quantity bought, never changed after creation) and its own
#     purchase cost per unit (unit_amount, falling back to taxable_unit_amount -
#     the same rule the existing purchase reports use).
#   * Sales are OrderItem rows. They store transaction-time amounts:
#     subtotal (taxable), gst_amount (CGST+SGST), igst_amount, total_price (incl. tax).
#     An invoice belongs to the financial year stored on its Order (by invoice date).
#     Deleted invoices are excluded everywhere.
#   * Supplier returns are ProductReturn rows (return_date, stock_returned, amounts).
#
# Inventory costing: SPECIFIC IDENTIFICATION per purchase lot.
#   Each sale and return points at the exact lot (Product row) it came from, so
#   remaining stock of a lot is valued at that lot's own historical purchase cost.
#   No averaging or FIFO assumption is needed, and selling prices are never used.
#
# Opening stock of a financial year = stock remaining at the end of 31 March of
# the previous year, from dated movements:
#     remaining(lot) = initial_stock - sold before 1 April - returned before 1 April
#     value          = remaining x lot purchase cost (taxable, excl. GST)
# It is CALCULATED, never stored, so it cannot be duplicated or counted twice,
# and it is never added to the purchases of the new year.
#
# Limitation (reported, not hidden): the Update Product form can overwrite a
# product's current quantity without recording a dated movement. Such edits
# cannot be placed in a past year; they show up as "untracked stock edits"
# (the gap between dated movements and the quantity currently on record).

from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Min, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from .models import (
    OrderItem, Product, ProductReturn,
    financial_year_bounds, format_financial_year, get_financial_year,
)

ZERO = Decimal('0.00')
CENT = Decimal('0.01')
UNCATEGORIZED = 'Uncategorized'
FY_MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
MONTH_ABBR = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
PAST_FY_COUNT = 10
MONEY = DecimalField(max_digits=16, decimal_places=2)


def q2(value):
    return (value or ZERO).quantize(CENT)


# ---------------------------------------------------------------- financial year

def current_fy(today=None):
    return get_financial_year(today or timezone.localdate())


def fy_choices(today=None, count=PAST_FY_COUNT):
    """[(2026, 'FY 2026-27'), (2025, 'FY 2025-26'), ...] current year first, then `count` past years."""
    cur = current_fy(today)
    return [(y, f'FY {format_financial_year(y)}') for y in range(cur, cur - count - 1, -1)]


def resolve_fy(value, today=None):
    """Accepts 2026, '2026', 'fy2026'; anything invalid or outside the offered years -> current FY."""
    cur = current_fy(today)
    try:
        year = int(str(value).lower().replace('fy', '').strip())
    except (TypeError, ValueError):
        return cur
    return year if cur - PAST_FY_COUNT <= year <= cur else cur


def fy_label(year):
    return f'FY {format_financial_year(year)}'


# ---------------------------------------------------------------- formatting

def format_inr(amount, signed=False):
    """Indian digit grouping: 500000 -> '₹5,00,000.00'. signed=True adds +/− (U+2212)."""
    amount = q2(Decimal(amount))
    sign = ''
    if signed and amount > 0:
        sign = '+'
    elif amount < 0:
        sign = '\u2212'
    whole, frac = f'{abs(amount):.2f}'.split('.')
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ','.join(groups + [tail])
    return f'{sign}\u20b9{whole}.{frac}'


def difference_display(purchase, sales):
    """
    Sales − Purchase (both incl. GST) for the financial year.
    Sales lower: red with '−'. Sales higher: green with '+'. Equal: neutral '₹0.00'.
    A comparison of transaction totals only - NOT profit (see profit_report for that).
    """
    diff = q2(sales) - q2(purchase)
    if diff > 0:
        tone = 'sales-higher'
    elif diff < 0:
        tone = 'purchase-higher'
    else:
        tone = 'neutral'
    return {'value': diff, 'text': format_inr(diff, signed=True), 'tone': tone}


def signed_display(value):
    """Profit-style display: positive green '+', negative red '−', zero neutral."""
    value = q2(value)
    tone = 'gain' if value > 0 else ('loss' if value < 0 else 'neutral')
    return {'value': value, 'text': format_inr(value, signed=True), 'tone': tone}


# ---------------------------------------------------------------- purchases

def lot_unit_cost(p):
    """Purchase cost per unit excl. GST - same rule as the existing purchase reports."""
    return p.unit_amount if p.unit_amount else (p.taxable_unit_amount or ZERO)


def lot_tax_rate(p):
    return p.igst if (p.igst or ZERO) > 0 else (p.gst or ZERO)


def _with_tax(taxable, rate):
    return taxable * (Decimal('1') + Decimal(rate) / Decimal('100'))


def _category(name):
    return (name or '').strip() or UNCATEGORIZED


def purchase_report(owner, fy):
    """Purchases DURING the financial year (purchase lots by purchase_date). Opening stock is NOT included."""
    start, end = financial_year_bounds(fy)
    lots = (Product.objects.filter(store_owner=owner, purchase_date__range=(start, end))
            .only('id', 'name', 'category', 'purchase_date', 'initial_stock', 'unit_amount',
                  'taxable_unit_amount', 'gst', 'igst', 'purchased_from', 'purchase_invoice_number'))
    months = OrderedDict((m, ZERO) for m in FY_MONTHS)
    items, totals = [], {'quantity': 0, 'taxable': ZERO, 'gross': ZERO, 'lots': 0}
    missing_cost = []
    for p in lots:
        if not lot_unit_cost(p) and p.initial_stock:
            missing_cost.append(p.name)
        taxable = lot_unit_cost(p) * p.initial_stock
        gross = _with_tax(taxable, lot_tax_rate(p))
        months[p.purchase_date.month] += gross
        totals['quantity'] += p.initial_stock
        totals['taxable'] += taxable
        totals['gross'] += gross
        totals['lots'] += 1
        items.append({'product_id': p.id, 'name': p.name, 'category': _category(p.category),
                      'quantity': p.initial_stock, 'taxable': taxable, 'gross': gross,
                      'date': p.purchase_date, 'supplier': p.purchased_from,
                      'invoice': p.purchase_invoice_number})
    returns = purchase_returns(owner, fy)
    return {
        'fy': fy,
        'items': _rollup_items(items),
        'categories': _rollup_categories(items),
        'monthly': [{'month': MONTH_ABBR[m], 'gross': q2(v)} for m, v in months.items()],
        'totals': {'quantity': totals['quantity'], 'taxable': q2(totals['taxable']),
                   'gross': q2(totals['gross']), 'lots': totals['lots']},
        'returns': returns,
        'net_gross': q2(totals['gross'] - returns['gross']),
        # Lots saved without any purchase cost are valued at 0 - never at a selling price - and listed here.
        'missing_cost': missing_cost,
    }


def purchase_returns(owner, fy):
    """Supplier returns dated in the financial year (stored amounts)."""
    start, end = financial_year_bounds(fy)
    agg = ProductReturn.objects.filter(product__store_owner=owner, return_date__range=(start, end)).aggregate(
        quantity=Coalesce(Sum('stock_returned'), 0),
        taxable=Coalesce(Sum('taxable_total_amount'), Value(ZERO), output_field=MONEY),
        gross=Coalesce(Sum('total_amount'), Value(ZERO), output_field=MONEY),
        count=Count('id'))
    return {'quantity': agg['quantity'], 'taxable': q2(agg['taxable']), 'gross': q2(agg['gross']), 'count': agg['count']}


# ---------------------------------------------------------------- sales

def _taxable_line():
    """Stored taxable subtotal; for old rows without it, total minus stored tax."""
    return Coalesce(
        F('subtotal'),
        ExpressionWrapper(F('total_price') - Coalesce(F('gst_amount'), Value(ZERO)) - Coalesce(F('igst_amount'), Value(ZERO)),
                          output_field=MONEY),
        output_field=MONEY)


def sales_lines(owner, fy):
    """Invoice lines of non-deleted invoices that belong to the financial year."""
    return OrderItem.objects.filter(order__store_owner=owner, order__is_deleted=False, order__financial_year=fy)


def sales_report(owner, fy):
    lines = sales_lines(owner, fy)
    per_product = (lines.values('product_id', 'product__name', 'product__category')
                   .annotate(quantity=Sum('quantity'),
                             gross=Coalesce(Sum('total_price'), Value(ZERO), output_field=MONEY),
                             taxable=Coalesce(Sum(_taxable_line()), Value(ZERO), output_field=MONEY))
                   .order_by())
    items = [{'product_id': r['product_id'], 'name': r['product__name'], 'category': _category(r['product__category']),
              'quantity': r['quantity'] or 0, 'gross': r['gross'], 'taxable': r['taxable']} for r in per_product]
    agg = lines.aggregate(gross=Coalesce(Sum('total_price'), Value(ZERO), output_field=MONEY),
                          taxable=Coalesce(Sum(_taxable_line()), Value(ZERO), output_field=MONEY),
                          quantity=Coalesce(Sum('quantity'), 0), invoices=Count('order', distinct=True))
    return {
        'fy': fy,
        'items': _rollup_items(items),
        'categories': _rollup_categories(items),
        'totals': {'quantity': agg['quantity'], 'taxable': q2(agg['taxable']), 'gross': q2(agg['gross']),
                   'invoices': agg['invoices']},
    }


# ---------------------------------------------------------------- profit

def profit_report(owner, fy):
    """
    Item-wise profit for invoices of the financial year (non-deleted, by invoice date - same basis as sales).

      Sales excl. GST  = stored taxable subtotal of each invoice line (actual invoice rate x quantity)
      Sales incl. GST  = stored line total
      Cost of qty sold = quantity sold from each lot x THAT lot's purchase cost (specific identification),
                         so partial sales, lots bought at different costs and stock carried in from
                         earlier years are all costed at what those units actually cost.
      Profit excl. GST = Sales excl. GST - Cost
      Profit incl. GST = Sales incl. GST - Cost   (requested GST-inclusive measure; includes output GST,
                                                   so it is not the conventional accounting profit)

    Rows are per item (product name + category); lots of the same item bought at different costs merge
    into one row. Revenue is aggregated by the database from stored amounts; cost is multiplied exactly
    in Python with Decimal (one row per lot).
    """
    start = financial_year_bounds(fy)[0]
    per_lot = (sales_lines(owner, fy).values('product_id')
               .annotate(quantity=Sum('quantity'),
                         taxable=Coalesce(Sum(_taxable_line()), Value(ZERO), output_field=MONEY),
                         gross=Coalesce(Sum('total_price'), Value(ZERO), output_field=MONEY),
                         min_rate=Min('item_price'), max_rate=Max('item_price'))
               .order_by())
    per_lot = {r['product_id']: r for r in per_lot}
    lots = {p.id: p for p in Product.objects.filter(id__in=per_lot).only(
        'id', 'name', 'category', 'purchase_date', 'unit_amount', 'taxable_unit_amount')}

    rows, missing_cost = OrderedDict(), []
    for pid, r in per_lot.items():
        p = lots[pid]
        cost = lot_unit_cost(p) * r['quantity']
        if not lot_unit_cost(p):
            missing_cost.append(p.name)
        key = (p.name.strip(), _category(p.category))
        row = rows.setdefault(key, {
            'name': key[0], 'category': key[1], 'quantity': 0, 'taxable': ZERO, 'gross': ZERO, 'cost': ZERO,
            'cost_from_opening_stock': ZERO, 'min_rate': r['min_rate'], 'max_rate': r['max_rate'], 'lots': 0,
        })
        row['quantity'] += r['quantity']
        row['taxable'] += r['taxable']
        row['gross'] += r['gross']
        row['cost'] += cost
        if p.purchase_date < start:           # sold out of stock carried in from earlier years
            row['cost_from_opening_stock'] += cost
        row['min_rate'] = min(row['min_rate'], r['min_rate'])
        row['max_rate'] = max(row['max_rate'], r['max_rate'])
        row['lots'] += 1

    items = []
    totals = {k: ZERO for k in ('taxable', 'gst', 'gross', 'cost', 'cost_from_opening_stock', 'profit_ex', 'profit_in')}
    totals['quantity'] = 0
    for row in rows.values():
        row['taxable'], row['gross'], row['cost'] = q2(row['taxable']), q2(row['gross']), q2(row['cost'])
        row['cost_from_opening_stock'] = q2(row['cost_from_opening_stock'])
        row['gst'] = row['gross'] - row['taxable']
        row['avg_rate'] = q2(row['taxable'] / row['quantity']) if row['quantity'] else ZERO
        row['profit_ex'] = row['taxable'] - row['cost']
        row['profit_in'] = row['gross'] - row['cost']
        row['profit_ex_display'] = signed_display(row['profit_ex'])
        row['profit_in_display'] = signed_display(row['profit_in'])
        for k in ('taxable', 'gst', 'gross', 'cost', 'cost_from_opening_stock', 'profit_ex', 'profit_in'):
            totals[k] += row[k]
        totals['quantity'] += row['quantity']
        items.append(row)
    items.sort(key=lambda r: (-r['profit_ex'], r['name']))
    return {
        'fy': fy,
        'items': items,
        'totals': totals,
        'profit_ex': signed_display(totals['profit_ex']),
        'profit_in': signed_display(totals['profit_in']),
        'loss_items': sum(1 for r in items if r['profit_ex'] < 0),
        'missing_cost': sorted(set(missing_cost)),
    }


# ---------------------------------------------------------------- inventory

def _sale_day():
    return Coalesce('order__invoice_date', TruncDate('order__order_date', tzinfo=timezone.get_current_timezone()))


def stock_position(owner, as_of):
    """
    Stock on hand at the START of `as_of` (movements dated before it), valued at each lot's purchase cost.
    Returns quantities and values; negative remainders (data inconsistencies) are counted as 0 and reported.
    """
    sold = dict(OrderItem.objects.filter(product__store_owner=owner, order__is_deleted=False)
                .annotate(day=_sale_day()).filter(day__lt=as_of)
                .values('product_id').annotate(q=Sum('quantity')).values_list('product_id', 'q'))
    returned = dict(ProductReturn.objects.filter(product__store_owner=owner, return_date__lt=as_of)
                    .values('product_id').annotate(q=Sum('stock_returned')).values_list('product_id', 'q'))
    lots = (Product.objects.filter(store_owner=owner, purchase_date__lt=as_of)
            .only('id', 'name', 'category', 'initial_stock', 'unit_amount', 'taxable_unit_amount', 'gst', 'igst'))
    qty, taxable, gross, anomalies, lines, missing_cost = 0, ZERO, ZERO, [], [], []
    for p in lots:
        remaining = p.initial_stock - (sold.get(p.id) or 0) - (returned.get(p.id) or 0)
        if remaining < 0:
            anomalies.append({'product_id': p.id, 'name': p.name, 'remaining': remaining})
            remaining = 0
        if remaining == 0:
            continue
        if not lot_unit_cost(p):
            missing_cost.append(p.name)
        value = lot_unit_cost(p) * remaining
        qty += remaining
        taxable += value
        gross += _with_tax(value, lot_tax_rate(p))
        lines.append({'product_id': p.id, 'name': p.name, 'category': _category(p.category),
                      'quantity': remaining, 'unit_cost': lot_unit_cost(p), 'value': value})
    return {'as_of': as_of, 'quantity': qty, 'value': q2(taxable), 'value_incl_gst': q2(gross),
            'lots': len(lines), 'lines': lines, 'anomalies': anomalies, 'missing_cost': missing_cost}


def opening_inventory(owner, fy):
    """Stock carried into the financial year: what remained at the end of 31 March of the previous year."""
    return stock_position(owner, financial_year_bounds(fy)[0])


def closing_inventory(owner, fy, today=None):
    """Stock at the end of the financial year, or to date for the year in progress."""
    today = today or timezone.localdate()
    end = financial_year_bounds(fy)[1]
    return stock_position(owner, min(end, today) + timedelta(days=1))


def cost_of_goods_sold(owner, fy):
    """Purchase cost (lot cost, excl. GST) of the quantity sold in the year. Uses invoice dates like stock_position."""
    start, end = financial_year_bounds(fy)
    rows = (OrderItem.objects.filter(product__store_owner=owner, order__is_deleted=False)
            .annotate(day=_sale_day()).filter(day__gte=start, day__lte=end)
            .values('product_id').annotate(q=Sum('quantity')))
    sold = {r['product_id']: r['q'] for r in rows}
    total = ZERO
    for p in Product.objects.filter(id__in=sold).only('id', 'unit_amount', 'taxable_unit_amount'):
        total += lot_unit_cost(p) * sold[p.id]
    return q2(total)


def returns_at_cost(owner, fy):
    """Supplier returns valued at the lot purchase cost (for the inventory roll-forward)."""
    start, end = financial_year_bounds(fy)
    total = ZERO
    for r in (ProductReturn.objects.filter(product__store_owner=owner, return_date__range=(start, end))
              .select_related('product').only('stock_returned', 'product__unit_amount', 'product__taxable_unit_amount')):
        total += lot_unit_cost(r.product) * r.stock_returned
    return q2(total)


def recorded_stock_value(owner):
    """Value of the quantity currently on record (Product.quantity) at lot cost - includes untracked edits."""
    qty, value = 0, ZERO
    for p in Product.objects.filter(store_owner=owner, quantity__gt=0).only('quantity', 'unit_amount', 'taxable_unit_amount'):
        qty += p.quantity
        value += lot_unit_cost(p) * p.quantity
    return {'quantity': qty, 'value': q2(value)}


def inventory_rollforward(owner, fy, today=None):
    """
    Opening stock + purchases (at cost) − supplier returns (at cost) − cost of goods sold = closing stock.
    All at purchase cost excl. GST. `balanced` is True when dated movements fully explain the closing stock.
    """
    today = today or timezone.localdate()
    opening = opening_inventory(owner, fy)
    closing = closing_inventory(owner, fy, today)
    purchases = purchase_report(owner, fy)['totals']['taxable']
    returns = returns_at_cost(owner, fy)
    cogs = cost_of_goods_sold(owner, fy)
    expected = opening['value'] + purchases - returns - cogs
    data = {
        'opening': opening, 'purchases': purchases, 'returns': returns, 'cogs': cogs,
        'closing': closing, 'expected_closing': q2(expected),
        'balanced': q2(expected) == closing['value'] and not closing['anomalies'] and not opening['anomalies'],
        'is_current_year': fy == current_fy(today),
    }
    if data['is_current_year']:
        rec = recorded_stock_value(owner)
        data['recorded'] = rec
        data['untracked_quantity'] = rec['quantity'] - closing['quantity']
        data['untracked_value'] = q2(rec['value'] - closing['value'])
    return data


# ---------------------------------------------------------------- dashboard summary

def fy_summary(owner, fy, today=None):
    """What the home page shows for a financial year. Purchases and sales are GST-inclusive; stock at cost."""
    purchases = purchase_report(owner, fy)
    sales = sales_report(owner, fy)
    opening = opening_inventory(owner, fy)
    diff = difference_display(purchases['totals']['gross'], sales['totals']['gross'])
    profit = profit_report(owner, fy)
    return {
        'fy': fy,
        'fy_label': fy_label(fy),
        'purchase': {'gross': purchases['totals']['gross'], 'text': format_inr(purchases['totals']['gross']),
                     'taxable_text': format_inr(purchases['totals']['taxable']), 'lots': purchases['totals']['lots'],
                     'returns_text': format_inr(purchases['returns']['gross']), 'returns': purchases['returns']['gross']},
        'sales': {'gross': sales['totals']['gross'], 'text': format_inr(sales['totals']['gross']),
                  'taxable_text': format_inr(sales['totals']['taxable']), 'invoices': sales['totals']['invoices']},
        'difference': diff,
        'opening_stock': {'value': opening['value'], 'text': format_inr(opening['value']),
                          'quantity': opening['quantity'], 'lots': opening['lots']},
        'monthly_purchases': purchases['monthly'],
        'profit_ex': profit['profit_ex'],
        'profit_in': profit['profit_in'],
        'profit_cost': profit['totals']['cost'],
    }


# ---------------------------------------------------------------- helpers

def _rollup_items(items):
    """Combine rows of the same product id (several lots never merge: each lot is its own product row)."""
    merged = OrderedDict()
    for it in items:
        row = merged.setdefault(it['product_id'], {**it, 'quantity': 0, 'taxable': ZERO, 'gross': ZERO})
        row['quantity'] += it['quantity']
        row['taxable'] += it['taxable']
        row['gross'] += it['gross']
    out = list(merged.values())
    for r in out:
        r['taxable'], r['gross'] = q2(r['taxable']), q2(r['gross'])
    out.sort(key=lambda r: (-r['gross'], r['name']))
    return out


def _rollup_categories(items):
    cats = OrderedDict()
    for it in items:
        c = cats.setdefault(it['category'], {'category': it['category'], 'quantity': 0, 'taxable': ZERO, 'gross': ZERO, 'products': 0})
        c['quantity'] += it['quantity']
        c['taxable'] += it['taxable']
        c['gross'] += it['gross']
    seen = {}
    for it in items:
        seen.setdefault(it['category'], set()).add(it['product_id'])
    out = []
    for name, c in cats.items():
        c['products'] = len(seen[name])
        c['taxable'], c['gross'] = q2(c['taxable']), q2(c['gross'])
        out.append(c)
    out.sort(key=lambda r: (-r['gross'], r['category']))
    return out


def category_comparison(purchase, sales):
    """Per category: purchases (incl. GST), sales (incl. GST), Sales − Purchase. Not profit."""
    names = OrderedDict()
    for c in purchase['categories'] + sales['categories']:
        names.setdefault(c['category'], None)
    p = {c['category']: c['gross'] for c in purchase['categories']}
    s = {c['category']: c['gross'] for c in sales['categories']}
    rows = []
    for name in names:
        pv, sv = p.get(name, ZERO), s.get(name, ZERO)
        rows.append({'category': name, 'purchase': pv, 'sales': sv, 'difference': difference_display(pv, sv)})
    rows.sort(key=lambda r: (-(r['purchase'] + r['sales']), r['category']))
    return rows
