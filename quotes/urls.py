from django.urls import path
from . import views
from . import client_portal_views

app_name = 'quotes'

urlpatterns = [
    # =====================================
    # MAIN DASHBOARD AND OVERVIEW ROUTES
    # =====================================
    path('', views.quote_dashboard, name='dashboard'),
    path('list/', views.quote_list, name='quote_list'),
    
    # =====================================
    # QUOTE CRUD OPERATIONS
    # =====================================
    path('create/', views.quote_create, name='quote_create'),
    path('create/client/<int:client_id>/', views.quote_create, name='quote_create_for_client'),
    path('<int:quote_id>/', views.quote_detail, name='quote_detail'),
    path('<int:quote_id>/builder/', views.quote_builder, name='quote_builder'),
    path('<int:quote_id>/edit/', views.quote_edit, name='quote_edit'),
    path('<int:quote_id>/duplicate/', views.quote_duplicate, name='quote_duplicate'),
    
    # =====================================
    # QUOTE WORKFLOW MANAGEMENT
    # =====================================
    path('<int:quote_id>/send/', views.send_quote, name='send_quote'),
    path('<int:quote_id>/update-status/', views.update_quote_status, name='update_quote_status'),
    path('<int:quote_id>/status-check/', views.quote_status_check, name='quote_status_check'),
    path('<int:quote_id>/approve/', views.approve_quote, name='approve_quote'),
    # path('<int:quote_id>/reject-approval/', views.reject_quote_approval, name='reject_quote_approval'),  # TODO: Implement reject_quote_approval view
    
    # =====================================
    # QUOTE ITEM MANAGEMENT (AJAX)
    # =====================================
    path('<int:quote_id>/items/add/', views.add_quote_item, name='add_quote_item'),
    path('<int:quote_id>/items/<int:item_id>/update/', views.update_quote_item, name='update_quote_item'),
    path('<int:quote_id>/items/<int:item_id>/remove/', views.remove_quote_item, name='remove_quote_item'),
    # path('<int:quote_id>/items/bulk-add/', views.bulk_add_items, name='bulk_add_items'),  # TODO: Implement bulk_add_items view
    # path('<int:quote_id>/items/reorder/', views.reorder_quote_items, name='reorder_quote_items'),  # TODO: Implement reorder_quote_items view
    
    # =====================================
    # PRODUCT SEARCH AND SELECTION
    # =====================================
    path('ajax/search-products/', views.search_products, name='search_products'),
    path('ajax/product-details/<int:product_id>/', views.get_product_details, name='get_product_details'),
    # path('ajax/browse-products/', views.browse_products, name='browse_products'),  # TODO: Implement browse_products view
    # path('ajax/browse-category/<int:category_id>/', views.browse_category, name='browse_category'),  # TODO: Implement browse_category view
    
    # =====================================
    # DOCUMENT GENERATION AND SHARING
    # =====================================
    path('<int:quote_id>/pdf/', views.generate_quote_pdf, name='generate_quote_pdf'),
    path('<int:quote_id>/email/', views.email_quote_to_client, name='email_quote_to_client'),
    # path('<int:quote_id>/print/', views.quote_print_view, name='quote_print_view'),  # TODO: Implement quote_print_view
    
    # =====================================
    # CLIENT PORTAL (PUBLIC ACCESS)
    # =====================================
    # path('<int:quote_id>/preview/', views.quote_preview, name='quote_preview'),  # TODO: Implement quote_preview view
    path('<int:quote_id>/preview/<str:access_token>/', client_portal_views.quote_preview_public, name='quote_preview_public'),
    path('<int:quote_id>/accept/<str:access_token>/', client_portal_views.quote_accept_public, name='quote_accept_public'),
    path('<int:quote_id>/feedback/<str:access_token>/', client_portal_views.quote_feedback_public, name='quote_feedback_public'),
    path('<int:quote_id>/download/<str:access_token>/', client_portal_views.quote_download_public, name='quote_download_public'),
    path('<int:quote_id>/contact/<str:access_token>/', client_portal_views.quote_contact_public, name='quote_contact_public'),
    
    # =====================================
    # QUOTE TEMPLATES AND AUTOMATION
    # TODO: Implement template management system
    # =====================================
    # path('templates/', views.quote_template_list, name='quote_template_list'),
    # path('templates/create/', views.quote_template_create, name='quote_template_create'),
    # path('templates/<int:template_id>/', views.quote_template_detail, name='quote_template_detail'),
    # path('<int:quote_id>/apply-template/<int:template_id>/', views.apply_quote_template, name='apply_quote_template'),
    # path('<int:quote_id>/save-as-template/', views.save_as_template, name='save_as_template'),
    
    # =====================================
    # BULK OPERATIONS AND MANAGEMENT
    # TODO: Implement bulk operations for efficiency
    # =====================================
    # path('bulk-update/', views.bulk_update_quotes, name='bulk_update_quotes'),
    # path('bulk-send/', views.bulk_send_quotes, name='bulk_send_quotes'),
    # path('bulk-export/', views.bulk_export_quotes, name='bulk_export_quotes'),
    
    # =====================================
    # ANALYTICS AND REPORTING
    # TODO: Implement analytics and reporting features
    # =====================================
    path('analytics/', views.quote_analytics, name='quote_analytics'),
    # path('analytics/performance/', views.quote_performance_report, name='quote_performance_report'),
    # path('analytics/client-analysis/', views.client_quote_analysis, name='client_quote_analysis'),
    # path('analytics/export/', views.export_quote_analytics, name='export_quote_analytics'),
    path('sales-report/', views.sales_report, name='sales_report'),

    
    # =====================================
    # INTEGRATION ENDPOINTS
    # TODO: Implement CRM integration endpoints
    # =====================================
    # path('ajax/client-quotes/<int:client_id>/', views.get_client_quotes, name='get_client_quotes'),
    # path('ajax/client-quote-stats/<int:client_id>/', views.get_client_quote_stats, name='get_client_quote_stats'),
    # path('ajax/check-availability/', views.check_product_availability, name='check_product_availability'),
    # path('ajax/get-pricing/<int:product_id>/', views.get_product_pricing, name='get_product_pricing'),
    
    # =====================================
    # UTILITY AND HELPER ENDPOINTS
    # =====================================
    # path('<int:quote_id>/auto-save/', views.auto_save_quote, name='auto_save_quote'),  # TODO: Implement auto-save functionality
    path('ajax/generate-quote-number/', views.generate_quote_number_ajax, name='generate_quote_number_ajax'),
    # path('ajax/validate-quote-number/', views.validate_quote_number, name='validate_quote_number'),  # TODO: Implement quote number validation
    path('ajax/convert-currency/', views.convert_currency, name='convert_currency'),
    path('ajax/dashboard-stats/', views.get_dashboard_stats, name='get_dashboard_stats'),
]
