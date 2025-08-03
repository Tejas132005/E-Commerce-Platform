from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone


def home(request):
    user = request.user
    show_plans = True

    if user.is_authenticated:
        if user.is_paid and user.subscription_expiry and user.subscription_expiry > timezone.now():
            show_plans = False

    return render(request, 'home.html', {
        'show_plans': show_plans,
    })

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


