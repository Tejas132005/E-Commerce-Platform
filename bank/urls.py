from django.urls import path

from . import views

urlpatterns = [
    path('', views.bank_payment_management, name='bank_payment_management'),
    path('delete/<int:pk>/', views.delete_bank_transaction, name='delete_bank_transaction'),
]
