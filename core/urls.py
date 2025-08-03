from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('docs/', views.docs, name='docs'),
    path('pricing/', views.pricing, name='pricing'),
    path('contact/', views.contact, name='contact'),

    path('history/', views.history, name='history'),
    path('stock-details/', views.stock_details, name='stock_details'),
    path('data-analysis/', views.data_analysis, name='data_analysis'),

    path("e-commerce/", views.eCommerce, name="e-commerce"),
]
