# inventory/urls.py - Complete URL Configuration for Electronics Business

"""
Complete URL routing for BlitzTech Electronics inventory management system.

Features:
1. Product management with dynamic attributes
2. Advanced cost calculation and pricing
3. Multi-location stock management
4. Reorder management and automation
5. Business intelligence and analytics
6. Barcode/QR code support
7. Bulk operations and data management
8. API endpoints for integration
9. Reporting and export functionality
"""

from django.urls import path, include
from . import views

app_name = 'inventory'

# =====================================
# MAIN DASHBOARD AND OVERVIEW
# =====================================

dashboard_patterns = [
    path('', views.InventoryDashboardView.as_view(), name='dashboard'),
    path('overview/', views.InventoryDashboardView.as_view(), name='overview'),
    path('analytics/', views.inventory_analytics_view, name='analytics'),
    path('low-stock-ordering/', views.LowStockOrderingView.as_view(), name='low_stock_ordering'),
]

# =====================================
# PRODUCT MANAGEMENT
# =====================================

product_patterns = [
    # Basic CRUD
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    # Advanced product operations
    path('products/<int:pk>/duplicate/', views.product_duplicate_view, name='product_duplicate'),
    path('products/<int:pk>/cost-analysis/', views.product_cost_analysis_view, name='product_cost_analysis'),
    path('products/bulk-create/', views.ProductBulkCreateView.as_view(), name='product_bulk_create'),
    path('products/bulk-update/', views.product_bulk_update_view, name='product_bulk_update'),
    path('products/bulk-import/', views.ProductBulkImportView.as_view(), name='product_bulk_import'),
    path('products/import-template/', views.product_import_template_view, name='product_import_template'),
    
    # Export and data management
    path('products/export/', views.product_export_view, name='product_export'),
    path('products/export-catalog/', views.product_catalog_export_view, name='product_catalog_export'),
    
    # Search and filtering
    path('products/search/', views.ProductSearchView.as_view(), name='product_search'),
    path('products/advanced-search/', views.ProductAdvancedSearchView.as_view(), name='product_advanced_search'),
]

# =====================================
# DYNAMIC CONFIGURATION MANAGEMENT
# =====================================

configuration_patterns = [
    # Currency management
    path('configuration/currencies/', views.CurrencyListView.as_view(), name='currency_list'),
    path('configuration/currencies/create/', views.CurrencyCreateView.as_view(), name='currency_create'),
    path('configuration/currencies/<int:pk>/edit/', views.CurrencyUpdateView.as_view(), name='currency_edit'),
    path('configuration/currencies/update-rates/', views.update_exchange_rates_view, name='update_exchange_rates'),
    
    # Overhead factors
    path('configuration/overhead-factors/', views.OverheadFactorListView.as_view(), name='overhead_factor_list'),
    path('configuration/overhead-factors/create/', views.OverheadFactorCreateView.as_view(), name='overhead_factor_create'),
    path('configuration/overhead-factors/<int:pk>/edit/', views.OverheadFactorUpdateView.as_view(), name='overhead_factor_edit'),
    
    # Product attributes
    path('configuration/attributes/', views.ProductAttributeListView.as_view(), name='product_attribute_list'),
    path('configuration/attributes/create/', views.ProductAttributeCreateView.as_view(), name='product_attribute_create'),
    path('configuration/attributes/<int:pk>/edit/', views.ProductAttributeUpdateView.as_view(), name='product_attribute_edit'),
    
    # Component families
    path('configuration/component-families/', views.ComponentFamilyListView.as_view(), name='component_family_list'),
    path('configuration/component-families/create/', views.ComponentFamilyCreateView.as_view(), name='component_family_create'),
    path('configuration/component-families/<int:pk>/edit/', views.ComponentFamilyUpdateView.as_view(), name='component_family_edit'),
    
    # Storage locations and bins
    path('configuration/locations/', views.StorageLocationListView.as_view(), name='storage_location_list'),
    path('configuration/locations/create/', views.StorageLocationCreateView.as_view(), name='storage_location_create'),
    path('configuration/locations/<int:pk>/edit/', views.StorageLocationUpdateView.as_view(), name='storage_location_edit'),
    path('configuration/locations/<int:location_id>/bins/', views.StorageBinListView.as_view(), name='storage_bin_list'),
    path('configuration/bins/create/', views.StorageBinCreateView.as_view(), name='storage_bin_create'),
    path('configuration/bins/<int:pk>/edit/', views.StorageBinUpdateView.as_view(), name='storage_bin_edit'),
]

# =====================================
# BUSINESS ENTITY MANAGEMENT
# =====================================

entity_patterns = [
    # Category management
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/products/', views.CategoryProductsView.as_view(), name='category_products'),
    
    # Brand management
    path('brands/', views.BrandListView.as_view(), name='brand_list'),
    path('brands/<int:pk>/', views.BrandDetailView.as_view(), name='brand_detail'),
    path('brands/create/', views.BrandCreateView.as_view(), name='brand_create'),
    path('brands/<int:pk>/edit/', views.BrandUpdateView.as_view(), name='brand_edit'),
    path('brands/<int:pk>/products/', views.BrandProductsView.as_view(), name='brand_products'),
    
    # Supplier management
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_edit'),
    path('suppliers/<int:pk>/products/', views.SupplierProductsView.as_view(), name='supplier_products'),
    path('suppliers/<int:pk>/performance/', views.SupplierPerformanceView.as_view(), name='supplier_performance'),
    path('suppliers/<int:pk>/contact/', views.supplier_contact_view, name='supplier_contact'),
]

# =====================================
# STOCK MANAGEMENT
# =====================================

stock_patterns = [
    # Stock level management
    path('stock/', views.StockOverviewView.as_view(), name='stock_overview'),
    path('stock/locations/', views.StockByLocationView.as_view(), name='stock_by_location'),
    path('stock/movements/', views.StockMovementListView.as_view(), name='stock_movement_list'),
    
    # Stock adjustments
    path('stock/adjust/', views.StockAdjustmentView.as_view(), name='stock_adjustment'),
    path('stock/transfer/', views.StockTransferView.as_view(), name='stock_transfer'),
    path('stock/bulk-adjust/', views.BulkStockAdjustmentView.as_view(), name='bulk_stock_adjustment'),
    
    # Stock takes (physical counting)
    path('stock/takes/', views.StockTakeListView.as_view(), name='stock_take_list'),
    path('stock/takes/create/', views.StockTakeCreateView.as_view(), name='stock_take_create'),
    path('stock/takes/<int:pk>/', views.StockTakeDetailView.as_view(), name='stock_take_detail'),
    path('stock/takes/<int:pk>/complete/', views.stock_take_complete_view, name='stock_take_complete'),
]

# =====================================
# REORDER MANAGEMENT
# =====================================

reorder_patterns = [
    # Reorder alerts and management
    path('reorders/', views.ReorderAlertListView.as_view(), name='reorder_alert_list'),
    path('reorders/generate-recommendations/', views.generate_reorder_recommendations_view, name='generate_reorder_recommendations'),
    path('reorders/download-list/', views.download_reorder_csv, name='download_reorder_csv'),
    path('reorders/bulk-create-alerts/', views.bulk_create_reorder_alerts_view, name='bulk_create_reorder_alerts'),
    path('reorders/<int:pk>/acknowledge/', views.acknowledge_reorder_alert_view, name='acknowledge_reorder_alert'),
    path('reorders/<int:pk>/complete/', views.complete_reorder_alert_view, name='complete_reorder_alert'),
    
    # Purchase order integration
    path('reorders/create-po/', views.create_purchase_order_from_alerts_view, name='create_po_from_alerts'),
]

# =====================================
# COST CALCULATION AND PRICING
# =====================================

pricing_patterns = [
    # Cost calculation tools
    path('pricing/calculator/', views.CostCalculatorView.as_view(), name='cost_calculator'),
    path('pricing/bulk-update/', views.BulkPriceUpdateView.as_view(), name='bulk_price_update'),
    path('pricing/margin-analysis/', views.MarginAnalysisView.as_view(), name='margin_analysis'),
    path('pricing/competitive-analysis/', views.CompetitivePricingView.as_view(), name='competitive_pricing'),
    
    # Markup management
    path('pricing/markup-rules/', views.MarkupRuleListView.as_view(), name='markup_rule_list'),
    path('pricing/markup-rules/create/', views.MarkupRuleCreateView.as_view(), name='markup_rule_create'),
    
    # Overhead cost management
    path('pricing/overhead-analysis/', views.OverheadAnalysisView.as_view(), name='overhead_analysis'),
]

# =====================================
# BARCODE AND QR CODE MANAGEMENT
# =====================================

barcode_patterns = [
    # QR Code generation and management
    path('barcodes/generator/', views.BarcodeGeneratorView.as_view(), name='barcode_generator'),
    path('barcodes/bulk-generate/', views.bulk_generate_barcodes_view, name='bulk_generate_barcodes'),
    path('barcodes/print-labels/', views.print_barcode_labels_view, name='print_barcode_labels'),
    
    # Barcode scanning interface
    path('barcodes/scanner/', views.BarcodeScannerView.as_view(), name='barcode_scanner'),
    path('barcodes/mobile-scanner/', views.MobileBarcodeScannerView.as_view(), name='mobile_barcode_scanner'),
]

# =====================================
# BUSINESS INTELLIGENCE AND REPORTS
# =====================================

reports_patterns = [
    # Main reports dashboard
    path('reports/', views.inventory_reports_view, name='reports'),
    
    # Standard inventory reports
    path('reports/stock-valuation/', views.stock_valuation_report, name='stock_valuation_report'),
    path('reports/low-stock/', views.low_stock_report, name='low_stock_report'),
    path('reports/stock-aging/', views.stock_aging_report, name='stock_aging_report'),
    path('reports/turnover-analysis/', views.inventory_turnover_report, name='inventory_turnover_report'),
    path('reports/abc-analysis/', views.abc_analysis_report, name='abc_analysis_report'),
    
    # Supplier and vendor reports
    path('reports/supplier-performance/', views.supplier_performance_report, name='supplier_performance_report'),
    path('reports/supplier-comparison/', views.supplier_comparison_report, name='supplier_comparison_report'),
    path('reports/purchase-analysis/', views.purchase_analysis_report, name='purchase_analysis_report'),
    
    # Financial and business reports
    path('reports/cost-analysis/', views.cost_analysis_report, name='cost_analysis_report'),
    path('reports/margin-analysis/', views.margin_analysis_report, name='margin_analysis_report'),
    path('reports/profitability/', views.profitability_report, name='profitability_report'),
    path('reports/tax-compliance/', views.tax_compliance_report, name='tax_compliance_report'),
    
    # Category and brand reports
    path('reports/category-analysis/', views.category_analysis_report, name='category_analysis_report'),
    path('reports/brand-performance/', views.brand_performance_report, name='brand_performance_report'),
    
    # Custom and advanced reports
    path('reports/custom/', views.CustomReportView.as_view(), name='custom_report'),
    path('reports/executive-summary/', views.executive_summary_report, name='executive_summary_report'),
]

# =====================================
# API ENDPOINTS
# =====================================

api_patterns = [
    # Product data APIs
    path('api/products/search/', views.product_search_api, name='product_search_api'),
    path('api/products/<int:product_id>/details/', views.product_details_api, name='product_details_api'),
    path('api/products/<int:product_id>/cost-calculation/', views.calculate_product_cost_api, name='product_cost_calculation_api'),
    path('api/products/<int:product_id>/stock-levels/', views.product_stock_levels_api, name='product_stock_levels_api'),
    
    # Dynamic attributes APIs
    path('api/component-families/<int:family_id>/attributes/', views.component_family_attributes_api, name='component_family_attributes_api'),
    path('api/products/<int:product_id>/attributes/', views.product_attributes_api, name='product_attributes_api'),
    
    # Stock management APIs
    path('api/stock/adjust/', views.stock_adjustment_api, name='stock_adjustment_api'),
    path('api/stock/levels/', views.stock_levels_api, name='stock_levels_api'),
    path('api/stock/movements/', views.stock_movements_api, name='stock_movements_api'),
    
    # Reorder management APIs
    path('api/reorders/generate-list/', views.generate_reorder_list_api, name='generate_reorder_list_api'),
    path('api/reorders/check-stock/', views.check_stock_availability_api, name='check_stock_availability_api'),
    path('api/reorders/recommendations/', views.reorder_recommendations_api, name='reorder_recommendations_api'),
    
    # Cost calculation APIs
    path('api/pricing/calculate/', views.calculate_product_cost_api, name='calculate_cost_api'),
    path('api/pricing/bulk-update/', views.bulk_price_update_api, name='bulk_price_update_api'),
    path('api/pricing/margin-analysis/', views.margin_analysis_api, name='margin_analysis_api'),
    
    # Barcode and QR code APIs
    path('api/barcodes/generate/<int:product_id>/', views.generate_barcode_api, name='generate_barcode_api'),
    path('api/qr-codes/generate/<int:product_id>/', views.product_qr_code_api, name='product_qr_code_api'),
    path('api/barcodes/lookup/<str:barcode>/', views.barcode_lookup_api, name='barcode_lookup_api'),
    path('api/qr-codes/scan/', views.qr_code_scan_api, name='qr_code_scan_api'),
    
    # Currency and exchange rate APIs
    path('api/currencies/rates/', views.currency_rates_api, name='currency_rates_api'),
    path('api/currencies/convert/', views.currency_convert_api, name='currency_convert_api'),
    path('api/currencies/update-rates/', views.update_exchange_rates_api, name='update_exchange_rates_api'),
    
    # Business intelligence APIs
    path('api/analytics/dashboard/', views.dashboard_analytics_api, name='dashboard_analytics_api'),
    path('api/analytics/category-performance/', views.category_performance_api, name='category_performance_api'),
    path('api/analytics/supplier-analysis/', views.supplier_country_analysis_api, name='supplier_analysis_api'),
    path('api/analytics/stock-trends/', views.stock_trends_api, name='stock_trends_api'),
    
    # Integration APIs (for quote system, etc.)
    path('api/integration/quote-products/', views.quote_products_api, name='quote_products_api'),
    path('api/integration/reserve-stock/', views.reserve_stock_api, name='reserve_stock_api'),
    path('api/integration/release-reservation/', views.release_reservation_api, name='release_reservation_api'),
    path('api/integration/product-availability/', views.product_availability_api, name='product_availability_api'),
]

# =====================================
# MOBILE AND FIELD OPERATIONS
# =====================================

mobile_patterns = [
    # Mobile interfaces
    path('mobile/', views.MobileDashboardView.as_view(), name='mobile_dashboard'),
    path('mobile/scanner/', views.MobileBarcodeScannerView.as_view(), name='mobile_scanner'),
    path('mobile/stock-check/', views.MobileStockCheckView.as_view(), name='mobile_stock_check'),
    path('mobile/quick-adjust/', views.mobile_quick_adjust_view, name='mobile_quick_adjust'),
    
    # Offline support APIs
    path('api/mobile/sync/', views.mobile_sync_api, name='mobile_sync_api'),
    path('api/mobile/offline-data/', views.mobile_offline_data_api, name='mobile_offline_data_api'),
    path('api/mobile/upload-batch/', views.mobile_upload_batch_api, name='mobile_upload_batch_api'),
]

# =====================================
# IMPORT/EXPORT AND DATA MANAGEMENT
# =====================================

data_management_patterns = [
    # Data import/export
    path('data/export/', views.DataExportView.as_view(), name='data_export'),
    path('data/import/', views.DataImportView.as_view(), name='data_import'),
    path('data/templates/', views.import_templates_view, name='import_templates'),
    
    # Data validation and cleanup
    path('data/validation/', views.data_validation_view, name='data_validation'),
    path('data/cleanup/', views.data_cleanup_view, name='data_cleanup'),
    path('data/duplicates/', views.find_duplicates_view, name='find_duplicates'),
    
    # Backup and restore
    path('data/backup/', views.data_backup_view, name='data_backup'),
    path('data/restore/', views.data_restore_view, name='data_restore'),
]

# =====================================
# SYSTEM ADMINISTRATION
# =====================================

admin_patterns = [
    # System health and monitoring
    path('admin/system-health/', views.system_health_view, name='system_health'),
    path('admin/performance-metrics/', views.performance_metrics_view, name='performance_metrics'),
    path('admin/audit-log/', views.audit_log_view, name='audit_log'),
    
    # Configuration management
    path('admin/system-settings/', views.system_settings_view, name='system_settings'),
    path('admin/maintenance/', views.system_maintenance_view, name='system_maintenance'),
    
    # User activity monitoring
    path('admin/user-activity/', views.user_activity_view, name='user_activity'),
    path('admin/permission-overview/', views.permission_overview_view, name='permission_overview'),
]

# =====================================
# COMBINE ALL URL PATTERNS
# =====================================

urlpatterns = [
    # Main dashboard (root)
    path('', views.InventoryDashboardView.as_view(), name='index'),
] + dashboard_patterns + product_patterns + configuration_patterns + entity_patterns + \
    stock_patterns + reorder_patterns + pricing_patterns + barcode_patterns + \
    reports_patterns + api_patterns + mobile_patterns + data_management_patterns + admin_patterns

# =====================================
# QUICK ACCESS SHORTCUTS
# =====================================

# Add some convenient shortcuts for common operations
urlpatterns += [
    # Quick access shortcuts
    path('quick/add-product/', views.QuickAddProductView.as_view(), name='quick_add_product'),
    path('quick/stock-check/', views.quick_stock_check_view, name='quick_stock_check'),
    path('quick/reorder/', views.quick_reorder_view, name='quick_reorder'),
    path('quick/cost-calc/', views.quick_cost_calculator_view, name='quick_cost_calculator'),
    
    # Dashboard widgets
    path('widgets/low-stock/', views.low_stock_widget_api, name='low_stock_widget'),
    path('widgets/top-products/', views.top_products_widget_api, name='top_products_widget'),
    path('widgets/supplier-alerts/', views.supplier_alerts_widget_api, name='supplier_alerts_widget'),
    path('widgets/cost-trends/', views.cost_trends_widget_api, name='cost_trends_widget'),
    
    # Search shortcuts
    path('search/', views.global_inventory_search, name='global_search'),
    path('search/suggestions/', views.search_suggestions_api, name='search_suggestions'),
    
    # Help and documentation
    path('help/', views.inventory_help_view, name='help'),
    path('help/getting-started/', views.getting_started_guide, name='getting_started'),
    path('help/cost-calculation/', views.cost_calculation_guide, name='cost_calculation_guide'),
    path('help/api-docs/', views.api_documentation_view, name='api_docs'),
]