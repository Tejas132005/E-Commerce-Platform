# store/fy_views.py - financial-year purchase / sales / comparison analytics pages (read-only).

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from . import fy_reports as R

KINDS = ('purchases', 'sales', 'compare', 'profit')


def _num(d):
    return float(d)


@login_required
def fy_analytics_view(request, kind):
    if kind not in KINDS:
        raise Http404
    owner = request.user
    fy = R.resolve_fy(request.GET.get('fy'))
    purchases = R.purchase_report(owner, fy)
    sales = R.sales_report(owner, fy)
    summary = R.fy_summary(owner, fy)
    ctx = {
        'kind': kind,
        'fy': fy,
        'fy_label': R.fy_label(fy),
        'fy_choices': R.fy_choices(),
        'summary': summary,
        'purchases': purchases,
        'sales': sales,
    }
    if kind == 'purchases':
        ctx['report'] = purchases
        ctx['chart'] = {
            'categories': [c['category'] for c in purchases['categories']],
            'values': [_num(c['gross']) for c in purchases['categories']],
            'months': [m['month'] for m in purchases['monthly']],
            'monthly': [_num(m['gross']) for m in purchases['monthly']],
        }
    elif kind == 'sales':
        ctx['report'] = sales
        ctx['chart'] = {
            'categories': [c['category'] for c in sales['categories']],
            'values': [_num(c['gross']) for c in sales['categories']],
        }
    elif kind == 'profit':
        profit = R.profit_report(owner, fy)
        ctx['profit'] = profit
        ctx['chart'] = {
            'names': [r['name'] for r in profit['items']],
            'categories': [r['category'] for r in profit['items']],
            'profit_ex': [_num(r['profit_ex']) for r in profit['items']],
            'profit_in': [_num(r['profit_in']) for r in profit['items']],
        }
    else:
        rows = R.category_comparison(purchases, sales)
        ctx['comparison'] = rows
        ctx['rollforward'] = R.inventory_rollforward(owner, fy)
        ctx['chart'] = {
            'categories': [r['category'] for r in rows],
            'purchase': [_num(r['purchase']) for r in rows],
            'sales': [_num(r['sales']) for r in rows],
        }
    return render(request, 'fy_analytics.html', ctx)
