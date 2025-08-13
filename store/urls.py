# store/urls.py

from django.urls import path
from . import views, manage_products

urlpatterns = [
    # Store owner dashboard and reports (for logged-in users)
    path('sales-report/', views.sales_report_view, name='sales_report'),
    path('sales-dashboard/', views.sales_dashboard_view, name='sales_dashboard'),

    # Personalized store URLs (public facing)
    path('<str:username>/', views.store_products_view, name='store_products'),
    path('<str:username>/product/<int:product_id>/', views.product_detail_view, name='product_detail'),
    path('<str:username>/add-to-cart/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('<str:username>/cart/', views.cart_view, name='cart_view'),
    path('<str:username>/checkout/', views.checkout_view, name='checkout'),
    path('<str:username>/orders/', views.my_orders_view, name='my_orders'),
    path('<str:username>/order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    
    # Invoice generation URLs - Updated
    path('<str:username>/invoice/<int:order_id>/', views.generate_invoice, name='generate_invoice'),
    path('<str:username>/invoice/<int:order_id>/pdf/', views.generate_invoice_pdf, name='generate_invoice_pdf'),

    # Customer authentication for specific stores
    path('<str:username>/login/', views.customer_login, name='customer_login'),
    path('<str:username>/register/', views.customer_register, name='customer_register'),
    path('<str:username>/logout/', views.customer_logout, name='customer_logout'),

    # Product management (for store owners)
    path('manage/add-product/', manage_products.add_new_product, name='add_product'),
    path('manage/update-product/', manage_products.update_existing_product, name='update_product'),
    path('manage/delete-product/', manage_products.delete_product, name='delete_product'),
    path('manage/products/', manage_products.product_list_view, name='product_list'),
]