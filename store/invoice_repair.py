# store/invoice_repair.py
#
# Repairs invoices whose financial_year is empty (NULL). That happens when old
# data reaches the new schema without going through the 0020 backfill, e.g.
#   - data loaded with loaddata / a DB restore AFTER `migrate`, or
#   - migrations regenerated locally with `makemigrations` (the backfill is lost).
#
# Without the repair, new invoices only "see" other new invoices and restart at 1.
#
# Rules:
#   1. Old (NULL-year) invoices keep the numbers they were issued with; only the
#      empty financial_year column is filled in (from invoice_date, else order_date).
#   2. If invoices were already created after the upgrade and their numbers clash
#      with old ones in the same financial year (e.g. a second INV-01), those NEWER
#      invoices are moved to continue after the highest old number (701, 702, ...).
#      Two invoices can't share one number in a financial year.
#   3. Nothing else changes: totals, items, stock, customers, dates stay as they are.
#
# Works with real models and with migration (historical) models.

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

DELETED_OFFSET = 1000000
TEMP_OFFSET = 3000000          # distinct from the 2000000 range used by resequencing


def _fy_of(order):
    if order.invoice_date:
        d = order.invoice_date
    elif order.order_date:
        dt = order.order_date
        d = timezone.localtime(dt).date() if timezone.is_aware(dt) else dt.date()
    else:
        d = timezone.localdate()
    return d.year if d.month >= 4 else d.year - 1


def _label(n):
    return f"INV-{n:02d}"


def repair_financial_years(Order, store_owner_id=None, dry_run=False):
    """
    Fill missing financial_year values and resolve number clashes.
    Returns a list of dicts describing what was (or, with dry_run, would be) changed.
    """
    base = Order.objects.all()
    if store_owner_id is not None:
        base = base.filter(store_owner_id=store_owner_id)
    missing = list(base.filter(financial_year__isnull=True)
                   .only('id', 'store_owner_id', 'invoice_date', 'order_date', 'order_number', 'is_deleted'))
    if not missing:
        return []

    # (owner, fy) -> legacy rows
    legacy = defaultdict(list)
    for o in missing:
        legacy[(o.store_owner_id, _fy_of(o))].append(o)

    report = []
    with transaction.atomic():
        for (owner_id, fy), rows in sorted(legacy.items()):
            legacy_numbers = {o.order_number for o in rows if not o.is_deleted and o.order_number < DELETED_OFFSET}
            legacy_max = max(legacy_numbers, default=0)

            # Invoices already created in this year by the new code
            existing = list(Order.objects.filter(store_owner_id=owner_id, financial_year=fy, is_deleted=False,
                                                 order_number__lt=DELETED_OFFSET)
                            .order_by('order_date', 'id').values_list('id', 'order_number', 'invoice_number'))
            clashing = [e for e in existing if e[1] <= legacy_max]
            keep_high = [e[1] for e in existing if e[1] > legacy_max]
            next_no = max([legacy_max] + keep_high) + 1

            moves = []
            for pk, old_no, old_label in clashing:
                moves.append({'id': pk, 'old': old_label or _label(old_no), 'new': _label(next_no), 'new_number': next_no})
                next_no += 1

            report.append({
                'store_owner_id': owner_id, 'financial_year': fy,
                'old_invoices_filled': len(rows), 'highest_old_number': legacy_max, 'renumbered': moves,
            })
            if dry_run:
                continue

            # 1. park clashing new invoices, 2. fill the year on old rows, 3. give parked rows their new numbers
            for m in moves:
                Order.objects.filter(pk=m['id']).update(order_number=TEMP_OFFSET + m['id'])
            Order.objects.filter(pk__in=[o.pk for o in rows]).update(financial_year=fy)
            for m in moves:
                Order.objects.filter(pk=m['id']).update(order_number=m['new_number'], invoice_number=m['new'])
    return report


def format_report(report, fy_label=lambda y: f"{y}-{(y + 1) % 100:02d}"):
    lines = []
    for r in report:
        lines.append(f"Store owner {r['store_owner_id']} | FY {fy_label(r['financial_year'])}: "
                     f"{r['old_invoices_filled']} old invoice(s) given their financial year "
                     f"(highest old number {r['highest_old_number']}).")
        for m in r['renumbered']:
            lines.append(f"    invoice id {m['id']}: {m['old']} -> {m['new']} (clashed with an old invoice)")
    return '\n'.join(lines) if lines else 'Nothing to repair: every invoice already has its financial year.'
