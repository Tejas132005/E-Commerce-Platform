# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse, HttpResponseBadRequest
from .forms import RegisterForm, LoginForm
from .models import CustomUser, Subscription
import stripe
from django.urls import reverse
from datetime import timedelta

stripe.api_key = settings.STRIPE_SECRET_KEY

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        company_name = request.POST.get('company_name')
        dob = request.POST.get('dob')
        location = request.POST.get('location')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            return render(request, 'register.html', {'error': 'Passwords do not match'})

        if CustomUser.objects.filter(email=email).exists():
            return render(request, 'register.html', {'error': 'Email already exists'})
        
        if CustomUser.objects.filter(phone=phone).exists():
            return render(request, 'register.html', {'error': 'Phone already exists'})

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            phone=phone,
            dob=dob,
            location=location,
            company_name=company_name,
            password=password1,
        )

        # Create subscription with default tier='free'
        Subscription.objects.create(user=user, tier='free')

        login(request, user)
        return redirect('home')

    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            phone = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, phone=phone, password=password)
            if user:
                login(request, user)
                return redirect('home')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def upgrade_to_pro(request):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'inr',
                'unit_amount': 100000,  # ₹1000
                'product_data': {'name': '300 Days Premium Plan'},
            },
            'quantity': 1,
        }],
        mode='payment',
        customer_email=request.user.email,
        # Redirect to payment success page instead of store directly
        success_url=request.build_absolute_uri('/accounts/payment-success/'),
        cancel_url=request.build_absolute_uri('/'),
    )
    return redirect(session.url, code=303)

@csrf_exempt
def stripe_webhook(request):
    print("🎯 Webhook called")

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        print("❌ Invalid payload:", e)
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print("❌ Invalid signature:", e)
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        email = session.get("customer_email")
        print(f"🎯 Webhook for email: {email}")

        if email:
            try:
                user = CustomUser.objects.get(email=email)
                user.is_paid = True
                user.subscription_expiry = (
                    user.subscription_expiry + timedelta(days=300)
                    if user.subscription_expiry and user.subscription_expiry > timezone.now()
                    else timezone.now() + timedelta(days=300)
                )
                user.save()

                Subscription.objects.update_or_create(
                    user=user,
                    defaults={'tier': 'pro'}
                )

                print(f"✅ Subscription upgraded for user with email {email}")
            except CustomUser.DoesNotExist:
                print(f"❌ No user found with email: {email}")
        else:
            print("❌ No customer_email found in session")

    else:
        print(f"⚠️ Unhandled event type: {event['type']}")

    return HttpResponse(status=200)

@login_required
def payment_success(request):
    """Payment success page that upgrades user and shows success message"""
    user = request.user
    user.is_paid = True
    user.subscription_expiry = (
        user.subscription_expiry + timedelta(days=300)
        if user.subscription_expiry and user.subscription_expiry > timezone.now()
        else timezone.now() + timedelta(days=300)
    )
    user.save()

    Subscription.objects.update_or_create(
        user=user,
        defaults={'tier': 'pro'}
    )

    # Show payment success page instead of redirecting immediately
    return render(request, 'payment_success.html', {
        'user': user,
        'store_url': reverse('store_products', kwargs={'username': user.username})
    })

def plan_view(request):
    return render(request, 'plan.html')