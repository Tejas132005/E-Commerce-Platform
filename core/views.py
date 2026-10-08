from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .dashboard import DEFAULT_RANGE, RANGE_CHOICES, build_home_dashboard, past_financial_years


def home(request):
    user = request.user
    show_plans = False
    context = {
        'show_plans': show_plans,
        'year': timezone.localdate().year,
    }
    if user.is_authenticated:
        dashboard = build_home_dashboard(user, request.GET.get('range', DEFAULT_RANGE))
        context.update({
            'dashboard': dashboard,
            'customer_count': dashboard['customer_count'],
            'range_choices': [(k, v[0]) for k, v in RANGE_CHOICES.items()],
            'past_fy_choices': past_financial_years(),
            'greeting': _greeting(),
        })
    return render(request, 'home.html', context)


def _greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 17:
        return 'Good afternoon'
    return 'Good evening'


@login_required
@never_cache
def home_stats(request):
    """JSON for the home charts; polled by the page so the graphs follow new sales."""
    return JsonResponse(build_home_dashboard(request.user, request.GET.get('range', DEFAULT_RANGE)))

def about(request):
    return render(request, 'about.html')

def docs(request):
    return render(request, 'docs.html')

def pricing(request):
    return render(request, 'pricing.html')

def contact(request):
    return render(request, 'contact.html')

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

@login_required
def history(request):
    return render(request, 'history.html')

@login_required
def stock_details(request):
    return render(request, 'stock_details.html')

@login_required
def data_analysis(request):
    return render(request, 'data_analysis.html')

@login_required
def eCommerce(request):
    
    return render(request, "")


