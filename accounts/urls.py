# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('plan/', views.plan_view, name='plan'),
    path('upgrade/', views.upgrade_to_pro, name='upgrade'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
]
