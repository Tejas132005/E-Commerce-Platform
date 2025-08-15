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
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Get all form data
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            company_name = form.cleaned_data['company_name']
            dob = form.cleaned_data['dob']
            location = form.cleaned_data['location']
            company_address = form.cleaned_data.get('company_address', '')
            company_city = form.cleaned_data.get('company_city', '')
            company_state = form.cleaned_data.get('company_state', '')
            company_pincode = form.cleaned_data.get('company_pincode', '')
            company_phone = form.cleaned_data.get('company_phone', '')
            company_email = form.cleaned_data.get('company_email', '')
            company_gstin = form.cleaned_data.get('company_gstin', '')
            password = form.cleaned_data['password']

            # Check for existing users
            if CustomUser.objects.filter(email=email).exists():
                form.add_error('email', 'Email already exists')
            elif CustomUser.objects.filter(phone=phone).exists():
                form.add_error('phone', 'Phone already exists')
            else:
                # Create user with all company details
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    phone=phone,
                    dob=dob,
                    location=location,
                    company_name=company_name,
                    company_address=company_address,
                    company_city=company_city,
                    company_state=company_state,
                    company_pincode=company_pincode,
                    company_phone=company_phone or phone,  # Use main phone if company phone not provided
                    company_email=company_email or email,  # Use main email if company email not provided
                    company_gstin=company_gstin,
                    password=password,
                )

                # Create subscription with default tier='free'
                Subscription.objects.create(user=user, tier='free')

                login(request, user)
                return redirect('home')
        else:
            # Form has errors, render with form errors
            return render(request, 'register.html', {'form': form})
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})

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