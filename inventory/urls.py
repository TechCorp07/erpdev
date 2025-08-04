# inventory/urls.py - Cleaned URL Configuration (Only Working Views)

"""
URL Routing for Inventory Management System

This URL configuration includes only the currently implemented views.
Future functionality is commented out with clear notes for implementation.

Currently Working:
- Basic dashboard and overview
- Product CRUD operations
- Basic stock management
- Simple category/supplier management
- API endpoints for product search and stock adjustments
- Quote system integration endpoints
- Export functionality

Future Implementation sections are clearly marked and commented.
"""

from django.urls import path, include
from . import views

app_name = 'inventory'

# =====================================
# WORKING URLS - CURRENTLY IMPLEMENTED
# =====================================

urlpatterns = [
    # Main dashboard (root inventory URL)
    path('', views.InventoryDashboardView.as_view(), name='dashboard'),
    
    # Dashboard and overview - WORKING
    path('overview/', views.InventoryOverviewView.as_view(), name='overview'),
    path('quick-stats/', views.quick_stats_api, name='quick_stats'),
    path('alerts/', views.inventory_alerts_view, name='alerts'),
    
    # Product management - WORKING BASIC CRUD
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('products/<int:pk>/duplicate/', views.product_duplicate_view, name='product_duplicate'),
    path('products/<int:pk>/adjust-stock/', views.adjust_stock_view, name='adjust_stock'),
    path('products/export/', views.product_export_view, name='product_export'),
    path('products/import/', views.product_import_view, name='product_import'),
    path('products/search/', views.ProductSearchView.as_view(), name='product_search'),
    path('products/bulk-import/', views.ProductBulkImportView.as_view(), name='bulk_import'),
    path('products/import-template/', views.product_import_template_excel, name='product_import_template_excel'),
    path('export/data/', views.export_data_view, name='export_data'),
    
    # Category management - WORKING BASIC CRUD
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    
    # Supplier management - WORKING BASIC CRUD
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    
    # Stock management - WORKING BASIC OPERATIONS
    path('stock/', views.StockOverviewView.as_view(), name='stock_overview'),
    path('stock/movements/', views.StockMovementListView.as_view(), name='stock_movements'),
    path('stock/transfer/', views.stock_transfer_view, name='stock_transfer'),
    path('stock/take-create/', views.stock_take_create, name='stock_take_create'),
    path('stock/adjust/', views.StockAdjustDashboardView.as_view(), name='stock_adjust'),
    path('stock-takes/', views.StockTakeListView.as_view(), name='stock_take_list'),
    path('stock-takes/<int:pk>/export/excel/', views.export_stock_take_excel, name='stock_take_export_excel'),
    path('stock-takes/<int:pk>/export/pdf/', views.export_stock_take_pdf, name='stock_take_export_pdf'),
    
    # API endpoints - WORKING
    path('api/products/search/', views.product_search_api, name='product_search_api'),
    path('api/products/check-sku/', views.check_sku_availability, name='check_sku_availability'),
    path('api/products/check-barcode/', views.check_barcode_availability, name='check_barcode_availability'),
    path('api/stock/adjust/', views.stock_adjust_api, name='stock_adjust_api'),
    path('api/dashboard/metrics/', views.dashboard_metrics_api, name='dashboard_metrics_api'),
    path('api/recent-activities/', views.recent_activities_api, name='recent_activities_api'),
    path('api/critical-alerts/', views.critical_alerts_api, name='critical_alerts_api'),
    path('api/live-stock/<int:product_id>/', views.get_live_stock, name='live_stock_api'),
    
    # Quote system integration - WORKING
    path('integrations/quote-products/', views.quote_products_api, name='quote_products_api'),
    path('integrations/check-availability/', views.check_quote_availability_api, name='check_quote_availability_api'),
    path('integrations/reserve-stock/', views.reserve_for_quote_api, name='reserve_for_quote_api'),
    
    # Quick access - WORKING
    path('quick-add-product/', views.QuickAddProductView.as_view(), name='quick_add_product'),
    path('quick-search/', views.quick_search_view, name='quick_search'),
    
    # Utility - WORKING
    path('help/', views.InventoryHelpView.as_view(), name='help'),
    path('settings/', views.InventorySettingsView.as_view(), name='settings'),
    
    path('reports/dashboard/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/valuation/', views.InventoryValuationReportView.as_view(), name='valuation_report'),
    path('reports/low-stock/', views.LowStockReportView.as_view(), name='low_stock_report'),
    path('reports/export/<str:report_type>/', views.export_report, name='export_report'),
    
    path('stock/movements/export/', views.stock_movements_export, name='stock_movements_export'),
    path('stock/low-stock/', views.low_stock_view, name='low_stock'),
    path('stock/adjust/', views.StockAdjustDashboardView.as_view(), name='stock_adjust'),
    path('suppliers/api/<int:pk>/details/', views.supplier_details_api, name='supplier_details_api'),
    
    path('alerts/dashboard/', views.AlertsDashboardView.as_view(), name='alerts_dashboard'),
    path('reorder-alerts/', views.reorder_alert_list, name='reorder_alert_list'),
]

# =====================================
# FUTURE IMPLEMENTATION - COMMENTED OUT
# =====================================

"""
# FUTURE: Advanced Product Management
# These URLs are for advanced product features not yet implemented:
# - Advanced search and filtering
# - Product analytics and performance
# - Bulk operations
# - Import functionality
# - Stock history and reservations

future_product_patterns = [
    path('products/search/', views.ProductSearchView.as_view(), name='product_search'),
    path('products/catalog/', views.ProductCatalogView.as_view(), name='product_catalog'),
    path('products/<int:pk>/stock/', views.ProductStockView.as_view(), name='product_stock'),
    path('products/<int:pk>/stock-history/', views.ProductStockHistoryView.as_view(), name='product_stock_history'),
    path('products/<int:pk>/reserve-stock/', views.reserve_stock_api, name='reserve_stock'),
    path('products/<int:pk>/release-stock/', views.release_stock_api, name='release_stock'),
    path('products/<int:pk>/analytics/', views.ProductAnalyticsView.as_view(), name='product_analytics'),
    path('products/<int:pk>/performance/', views.ProductPerformanceView.as_view(), name='product_performance'),
    path('products/bulk-update/', views.ProductBulkUpdateView.as_view(), name='product_bulk_update'),
    path('products/bulk-adjust-stock/', views.bulk_stock_adjustment_view, name='bulk_adjust_stock'),
    path('products/bulk-price-update/', views.bulk_price_update_view, name='bulk_price_update'),
    path('products/import/', views.ProductImportView.as_view(), name='product_import'),
    path('products/import-template/', views.product_import_template, name='product_import_template'),
]

# FUTURE: Advanced Category Management  
# These URLs are for category features beyond basic CRUD:
# - Category analytics
# - Bulk operations on category products
# - Category hierarchy management
# - Performance metrics

future_category_patterns = [
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail_slug'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('categories/<int:pk>/products/', views.CategoryProductsView.as_view(), name='category_products'),
    path('categories/<int:pk>/apply-defaults/', views.apply_category_defaults_view, name='apply_category_defaults'),
    path('categories/<int:pk>/bulk-update-products/', views.category_bulk_update_products, name='category_bulk_update_products'),
    path('categories/<int:pk>/analytics/', views.CategoryAnalyticsView.as_view(), name='category_analytics'),
    path('categories/<int:pk>/performance/', views.CategoryPerformanceView.as_view(), name='category_performance'),
    path('categories/api/hierarchy/', views.category_hierarchy_api, name='category_hierarchy_api'),
    path('categories/api/<int:pk>/products-count/', views.category_products_count_api, name='category_products_count_api'),
]

# FUTURE: Advanced Supplier Management
# These URLs are for supplier features beyond basic CRUD:
# - Supplier performance tracking
# - Purchase order integration
# - Supplier analytics and reports
# - Communication features

future_supplier_patterns = [
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
    path('suppliers/<int:pk>/products/', views.SupplierProductsView.as_view(), name='supplier_products'),
    path('suppliers/<int:pk>/purchase-orders/', views.SupplierPurchaseOrdersView.as_view(), name='supplier_purchase_orders'),
    path('suppliers/<int:pk>/performance/', views.SupplierPerformanceView.as_view(), name='supplier_performance'),
    path('suppliers/<int:pk>/contact/', views.supplier_contact_view, name='supplier_contact'),
    path('suppliers/<int:pk>/analytics/', views.SupplierAnalyticsView.as_view(), name='supplier_analytics'),
    path('suppliers/<int:pk>/price-history/', views.SupplierPriceHistoryView.as_view(), name='supplier_price_history'),
    path('suppliers/bulk-update/', views.SupplierBulkUpdateView.as_view(), name='supplier_bulk_update'),
    path('suppliers/export/', views.supplier_export_view, name='supplier_export'),
    path('suppliers/api/search/', views.supplier_search_api, name='supplier_search_api'),
]

# FUTURE: Location Management System
# Complete multi-location inventory management:
# - Location CRUD operations
# - Stock transfers between locations
# - Location capacity management
# - Location-specific analytics

future_location_patterns = [
    path('locations/', views.LocationListView.as_view(), name='location_list'),
    path('locations/<int:pk>/', views.LocationDetailView.as_view(), name='location_detail'),
    path('locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/edit/', views.LocationUpdateView.as_view(), name='location_edit'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    path('locations/<int:pk>/stock/', views.LocationStockView.as_view(), name='location_stock'),
    path('locations/<int:pk>/transfer-from/', views.location_transfer_from_view, name='location_transfer_from'),
    path('locations/<int:pk>/transfer-to/', views.location_transfer_to_view, name='location_transfer_to'),
    path('locations/<int:pk>/capacity/', views.LocationCapacityView.as_view(), name='location_capacity'),
    path('locations/<int:pk>/analytics/', views.LocationAnalyticsView.as_view(), name='location_analytics'),
    path('locations/<int:pk>/utilization/', views.LocationUtilizationView.as_view(), name='location_utilization'),
    path('locations/api/stock-levels/', views.location_stock_levels_api, name='location_stock_levels_api'),
    path('locations/api/<int:pk>/availability/', views.location_availability_api, name='location_availability_api'),
]

# FUTURE: Advanced Stock Management
# Enhanced stock operations and tracking:
# - Advanced stock level views
# - Bulk stock operations
# - Stock valuation and aging reports
# - Turnover analysis

future_stock_patterns = [
    path('stock/levels/', views.StockLevelsView.as_view(), name='stock_levels'),
    path('stock/low-stock/', views.LowStockView.as_view(), name='low_stock'),
    path('stock/out-of-stock/', views.OutOfStockView.as_view(), name='out_of_stock'),
    path('stock/movements/<int:pk>/', views.StockMovementDetailView.as_view(), name='stock_movement_detail'),
    path('stock/adjust/', views.StockAdjustmentView.as_view(), name='stock_adjust'),
    path('stock/bulk-adjust/', views.BulkStockAdjustmentView.as_view(), name='bulk_stock_adjust'),
    path('stock/valuation/', views.StockValuationView.as_view(), name='stock_valuation'),
    path('stock/aging/', views.StockAgingView.as_view(), name='stock_aging'),
    path('stock/turnover/', views.StockTurnoverView.as_view(), name='stock_turnover'),
    path('stock/api/levels/', views.stock_levels_api, name='stock_levels_api'),
    path('stock/api/movement-summary/', views.stock_movement_summary_api, name='stock_movement_summary_api'),
    path('stock/api/transfer/', views.stock_transfer_api, name='stock_transfer_api'),
]

# FUTURE: Purchase Order Management
# Complete purchase order workflow:
# - PO creation and management
# - Supplier communication
# - Receiving and tracking
# - Analytics and reporting

future_purchase_order_patterns = [
    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    path('purchase-orders/create/', views.PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('purchase-orders/<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='purchase_order_edit'),
    path('purchase-orders/<int:pk>/delete/', views.PurchaseOrderDeleteView.as_view(), name='purchase_order_delete'),
    path('purchase-orders/<int:pk>/send/', views.send_purchase_order_view, name='send_purchase_order'),
    path('purchase-orders/<int:pk>/acknowledge/', views.acknowledge_purchase_order_view, name='acknowledge_purchase_order'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order_view, name='receive_purchase_order'),
    path('purchase-orders/<int:pk>/cancel/', views.cancel_purchase_order_view, name='cancel_purchase_order'),
    path('purchase-orders/<int:po_id>/items/', views.PurchaseOrderItemsView.as_view(), name='purchase_order_items'),
    path('purchase-orders/<int:po_id>/items/add/', views.add_purchase_order_item_view, name='add_purchase_order_item'),
    path('purchase-orders/<int:po_id>/items/<int:item_id>/edit/', views.edit_purchase_order_item_view, name='edit_purchase_order_item'),
    path('purchase-orders/<int:po_id>/items/<int:item_id>/receive/', views.receive_purchase_order_item_view, name='receive_purchase_order_item'),
    path('purchase-orders/<int:pk>/pdf/', views.purchase_order_pdf_view, name='purchase_order_pdf'),
    path('purchase-orders/<int:pk>/email/', views.email_purchase_order_view, name='email_purchase_order'),
    path('purchase-orders/<int:pk>/print/', views.print_purchase_order_view, name='print_purchase_order'),
    path('purchase-orders/analytics/', views.PurchaseOrderAnalyticsView.as_view(), name='purchase_order_analytics'),
    path('purchase-orders/<int:pk>/performance/', views.PurchaseOrderPerformanceView.as_view(), name='purchase_order_performance'),
    path('purchase-orders/api/search/', views.purchase_order_search_api, name='purchase_order_search_api'),
    path('purchase-orders/api/<int:pk>/status/', views.purchase_order_status_api, name='purchase_order_status_api'),
    path('purchase-orders/api/generate-from-alerts/', views.generate_po_from_alerts_api, name='generate_po_from_alerts_api'),
]

# FUTURE: Reorder Alert Management
# Automated reorder point management:
# - Alert generation and management
# - Bulk operations on alerts
# - Analytics and recommendations
# - PO generation from alerts

future_reorder_patterns = [
    path('reorder-alerts/', views.ReorderAlertListView.as_view(), name='reorder_alert_list'),
    path('reorder-alerts/<int:pk>/', views.ReorderAlertDetailView.as_view(), name='reorder_alert_detail'),
    path('reorder-alerts/<int:pk>/acknowledge/', views.acknowledge_reorder_alert_view, name='acknowledge_reorder_alert'),
    path('reorder-alerts/<int:pk>/resolve/', views.resolve_reorder_alert_view, name='resolve_reorder_alert'),
    path('reorder-alerts/<int:pk>/create-po/', views.create_po_from_alert_view, name='create_po_from_alert'),
    path('reorder-alerts/bulk-acknowledge/', views.bulk_acknowledge_alerts_view, name='bulk_acknowledge_alerts'),
    path('reorder-alerts/bulk-create-po/', views.bulk_create_po_from_alerts_view, name='bulk_create_po_from_alerts'),
    path('reorder-alerts/bulk-resolve/', views.bulk_resolve_alerts_view, name='bulk_resolve_alerts'),
    path('reorder-alerts/analytics/', views.ReorderAnalyticsView.as_view(), name='reorder_analytics'),
    path('reorder-alerts/recommendations/', views.ReorderRecommendationsView.as_view(), name='reorder_recommendations'),
    path('reorder-alerts/api/active/', views.active_reorder_alerts_api, name='active_reorder_alerts_api'),
    path('reorder-alerts/api/priority/<str:priority>/', views.priority_reorder_alerts_api, name='priority_reorder_alerts_api'),
    path('reorder-alerts/api/generate/', views.generate_reorder_alerts_api, name='generate_reorder_alerts_api'),
]

# FUTURE: Stock Take Management
# Physical inventory counting system:
# - Stock take planning and execution
# - Variance tracking and resolution
# - Approval workflows
# - Reporting and analysis

future_stock_take_patterns = [
    path('stock-takes/<int:pk>/', views.StockTakeDetailView.as_view(), name='stock_take_detail'),
    path('stock-takes/create/', views.StockTakeCreateView.as_view(), name='stock_take_create'),
    path('stock-takes/<int:pk>/edit/', views.StockTakeUpdateView.as_view(), name='stock_take_edit'),
    path('stock-takes/<int:pk>/delete/', views.StockTakeDeleteView.as_view(), name='stock_take_delete'),
    path('stock-takes/<int:pk>/start/', views.start_stock_take_view, name='start_stock_take'),
    path('stock-takes/<int:pk>/complete/', views.complete_stock_take_view, name='complete_stock_take'),
    path('stock-takes/<int:pk>/approve/', views.approve_stock_take_view, name='approve_stock_take'),
    path('stock-takes/<int:pk>/cancel/', views.cancel_stock_take_view, name='cancel_stock_take'),
    path('stock-takes/<int:pk>/items/', views.StockTakeItemsView.as_view(), name='stock_take_items'),
    path('stock-takes/<int:pk>/count/', views.StockTakeCountingView.as_view(), name='stock_take_counting'),
    path('stock-takes/<int:pk>/count/<int:item_id>/', views.count_stock_take_item_view, name='count_stock_take_item'),
    path('stock-takes/<int:pk>/variances/', views.StockTakeVariancesView.as_view(), name='stock_take_variances'),
    path('stock-takes/<int:pk>/report/', views.StockTakeReportView.as_view(), name='stock_take_report'),
    path('stock-takes/<int:pk>/adjustments/', views.StockTakeAdjustmentsView.as_view(), name='stock_take_adjustments'),
    path('stock-takes/<int:pk>/pdf/', views.stock_take_pdf_view, name='stock_take_pdf'),
    path('stock-takes/api/items/<int:pk>/', views.stock_take_items_api, name='stock_take_items_api'),
    path('stock-takes/api/count/', views.stock_take_count_api, name='stock_take_count_api'),
    path('stock-takes/api/<int:pk>/summary/', views.stock_take_summary_api, name='stock_take_summary_api'),
]

# FUTURE: Comprehensive Reporting System
# Advanced analytics and reporting:
# - Inventory valuation reports
# - Performance analytics
# - ABC analysis
# - Custom report builder
# - Scheduled reports

future_reports_patterns = [
    path('reports/', views.ReportsDashboardView.as_view(), name='reports_dashboard'),
    path('reports/inventory-valuation/', views.InventoryValuationReportView.as_view(), name='inventory_valuation_report'),
    path('reports/stock-levels/', views.StockLevelsReportView.as_view(), name='stock_levels_report'),
    path('reports/low-stock/', views.LowStockReportView.as_view(), name='low_stock_report'),
    path('reports/stock-movement/', views.StockMovementReportView.as_view(), name='stock_movement_report'),
    path('reports/abc-analysis/', views.ABCAnalysisReportView.as_view(), name='abc_analysis_report'),
    path('reports/purchase-analysis/', views.PurchaseAnalysisReportView.as_view(), name='purchase_analysis_report'),
    path('reports/supplier-performance/', views.SupplierPerformanceReportView.as_view(), name='supplier_performance_report'),
    path('reports/cost-analysis/', views.CostAnalysisReportView.as_view(), name='cost_analysis_report'),
    path('reports/turnover-analysis/', views.TurnoverAnalysisReportView.as_view(), name='turnover_analysis_report'),
    path('reports/profit-margin/', views.ProfitMarginReportView.as_view(), name='profit_margin_report'),
    path('reports/demand-forecast/', views.DemandForecastReportView.as_view(), name='demand_forecast_report'),
    path('reports/custom/', views.CustomReportBuilderView.as_view(), name='custom_report_builder'),
    path('reports/custom/<int:report_id>/', views.CustomReportView.as_view(), name='custom_report_view'),
    path('reports/export/<str:report_type>/', views.export_report_view, name='export_report'),
    path('reports/schedule-report/', views.schedule_report_view, name='schedule_report'),
    path('reports/api/dashboard-metrics/', views.dashboard_metrics_api, name='dashboard_metrics_api'),
    path('reports/api/chart-data/<str:chart_type>/', views.chart_data_api, name='chart_data_api'),
]

# FUTURE: Mobile and Advanced API Endpoints
# Enhanced API for mobile apps and integrations:
# - Dashboard APIs
# - Barcode scanning
# - Mobile synchronization
# - Real-time updates

future_api_patterns = [
    path('api/dashboard/', views.dashboard_api, name='dashboard_api'),
    path('api/search/', views.global_search_api, name='global_search_api'),
    path('api/notifications/', views.inventory_notifications_api, name='inventory_notifications_api'),
    path('api/barcode/scan/', views.barcode_scan_api, name='barcode_scan_api'),
    path('api/barcode/lookup/<str:barcode>/', views.barcode_lookup_api, name='barcode_lookup_api'),
    path('api/qr/generate/<int:product_id>/', views.generate_qr_code_api, name='generate_qr_code_api'),
    path('api/mobile/sync/', views.mobile_sync_api, name='mobile_sync_api'),
    path('api/mobile/offline-data/', views.mobile_offline_data_api, name='mobile_offline_data_api'),
    path('api/mobile/upload-batch/', views.mobile_upload_batch_api, name='mobile_upload_batch_api'),
    path('api/live/stock-levels/', views.live_stock_levels_api, name='live_stock_levels_api'),
    path('api/live/alerts/', views.live_alerts_api, name='live_alerts_api'),
    path('api/live/notifications/', views.live_notifications_api, name='live_notifications_api'),
]

# FUTURE: Extended Integration Endpoints
# Advanced integrations with other systems:
# - Enhanced quote system integration
# - CRM integration
# - Financial system integration
# - External webhooks

future_integration_patterns = [
    path('integrations/release-reservation/', views.release_quote_reservation_api, name='release_quote_reservation_api'),
    path('integrations/customer-products/', views.customer_products_api, name='customer_products_api'),
    path('integrations/purchase-history/', views.customer_purchase_history_api, name='customer_purchase_history_api'),
    path('integrations/valuations/', views.inventory_valuations_api, name='inventory_valuations_api'),
    path('integrations/cost-updates/', views.cost_updates_api, name='cost_updates_api'),
    path('integrations/webhooks/supplier-update/', views.supplier_update_webhook, name='supplier_update_webhook'),
    path('integrations/webhooks/price-update/', views.price_update_webhook, name='price_update_webhook'),
]

# FUTURE: Additional Utility Features
# Enhanced utility and maintenance features:
# - Advanced audit logging
# - System maintenance tools
# - Data validation tools
# - Backup and restore functionality

future_utility_patterns = [
    path('audit-log/', views.InventoryAuditLogView.as_view(), name='audit_log'),
    path('quick-adjust-stock/', views.quick_adjust_stock_view, name='quick_adjust_stock'),
]

"""