from django import template

from store.fy_reports import format_inr

register = template.Library()


@register.filter
def inr(value):
    """Indian currency format: 569551.5 -> '₹5,69,551.50'."""
    try:
        return format_inr(value)
    except Exception:
        return value
