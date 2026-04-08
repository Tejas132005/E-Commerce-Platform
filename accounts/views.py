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
from django.urls import reverse
from datetime import timedelta

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
                    company_phone=company_phone or phone,  
                    company_email=company_email or email,  
                    company_gstin=company_gstin,
                    password=password,
                )

                # Create subscription with default tier='pro' (Removing Stripe requirement)
                user.is_paid = True
                user.subscription_expiry = timezone.now() + timedelta(days=3650) # 10 years
                user.save()
                
                Subscription.objects.create(user=user, tier='pro')

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
