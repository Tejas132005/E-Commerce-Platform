# E-Commerce/urls.py
from django.contrib import admin
from django.urls import path, include
from accounts import views as account_views  # for direct mapping

urlpatterns = [
    path('admin/', admin.site.urls),

    # # Auth + Stripe endpoints
    # path('register/', account_views.register_view, name='register'),
    # path('login/', account_views.login_view, name='login'),
    # path('logout/', account_views.logout_view, name='logout'),
    # path('plan/', account_views.plan_view, name='plan'),
    # path('upgrade/', account_views.upgrade_to_pro, name='upgrade'),
    # path('payment-success/', account_views.payment_success, name='payment_success'),
    # path('stripe-webhook/', account_views.stripe_webhook, name='stripe_webhook'),

    # Other App URLs
    path('', include('accounts.urls')),
    path('', include('core.urls')),
]
