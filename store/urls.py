# store/urls.py 

from django.urls import path
from . import views, manage_products, analytics

urlpatterns = [ 
    # Store owner dashboard and reports (for logged-in users)
    path('sales-report/', views.sales_report_view, name='sales_report'),
    path('sales-dashboard/', views.sales_dashboard_view, name='sales_dashboard'),
    
    # Stock Reports
    path('monthly-stock-report/', views.monthly_stock_report, name='monthly_stock_report'),
    path('yearly-stock-summary/', views.yearly_stock_summary, name='yearly_stock_summary'),
         
    # Global Analytics (uses request.user)
    path('analytics-dashboard/', views.analytics_dashboard_view, name='analytics_dashboard'),
    path('analytics/items/', analytics.item_analytics_api, name='item_analytics_api'),
    path('analytics/ad-section/', analytics.ad_section_page, name='ad_section_page'),
    path('analytics/api/ad-section/', analytics.ad_section_api, name='ad_section_api'),
    path('analytics/ad-section/export/', analytics.export_ad_section_csv, name='export_ad_section_csv'),
    path('analytics/item/<int:product_id>/', analytics.single_item_analytics_api, name='single_item_analytics_api'),
    path('analytics/categories/', analytics.category_analytics_api, name='category_analytics_api'),
         
    # User-specific Analytics (uses username parameter)
    path('<str:username>/analytics/', views.user_analytics_dashboard_view, name='user_analytics_dashboard'),
    path('<str:username>/analytics/items/', analytics.user_item_analytics_api, name='user_item_analytics_api'),
    path('<str:username>/analytics/item/<int:product_id>/', analytics.user_single_item_analytics_api, name='user_single_item_analytics_api'),
    path('<str:username>/analytics/categories/', analytics.user_category_analytics_api, name='user_category_analytics_api'),

    # Product management (for store owners)
    path('manage/add-product/', manage_products.add_new_product, name='add_product'),
    path('manage/update-product/<int:product_id>/', manage_products.update_existing_product, name='update_product_id'),
    path('manage/update-product/', manage_products.update_existing_product, name='update_product'),
    path('manage/delete-product/<int:product_id>/', manage_products.delete_product, name='delete_product_id'),
    path('manage/delete-product/', manage_products.delete_product, name='delete_product'),
    path('manage/products/', manage_products.product_list_view, name='product_list'),
    path('manage/product/<int:product_id>/details/', manage_products.product_manage_detail, name='product_manage_detail'),
    path('manage/customers/', views.customer_details_list_view, name='customer_details_list'),

    # Archive system
    path('manage/archive/<int:product_id>/', manage_products.archive_product, name='archive_product'),
    path('manage/unarchive/<int:product_id>/', manage_products.unarchive_product, name='unarchive_product'),
    path('manage/archived/', manage_products.archived_products_view, name='archived_products'),

    # Personalized store URLs (public facing)
    path('<str:username>/', views.store_products_view, name='store_products'),
    path('<str:username>/product/<int:product_id>/', views.product_detail_view, name='product_detail'),
    path('<str:username>/add-to-cart/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('<str:username>/cart/remove/<int:cart_item_id>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('<str:username>/cart/', views.cart_view, name='cart_view'),
    path('<str:username>/checkout/', views.checkout_view, name='checkout'),
    path('<str:username>/orders/', views.my_orders_view, name='my_orders'),
         
    path('<str:username>/order/<int:order_id>/', views.order_detail_view, name='order_detail_view'),
         
    # Invoice generation URLs
    path('<str:username>/invoice/<int:order_id>/', views.generate_invoice_view, name='generate_invoice_view'),
    path('<str:username>/invoice/<int:order_id>/pdf/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('<str:username>/invoice/<int:order_id>/download/', views.generate_invoice, name='generate_invoice'),

    # Customer authentication for specific stores
    path('<str:username>/login/', views.customer_login, name='customer_login'),
    path('<str:username>/register/', views.customer_register, name='customer_register'),
    path('<str:username>/logout/', views.customer_logout, name='customer_logout'),
]