# inventory/views.py - Inventory Management Views

"""
Django Views for Inventory Management System

Key Features:
1. Dynamic attribute handling per component family
2. Advanced cost calculation with overhead factors
3. Multi-currency support with real-time conversion
4. Automated low stock ordering lists
5. Barcode/QR code support
6. Advanced search with electronics-specific filters
7. Business intelligence dashboards
8. Integration with quote system
9. Comprehensive reporting
"""

import base64
from io import BytesIO
import json
import csv
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.template.loader import render_to_string
import qrcode
import requests
from weasyprint import HTML
from django.db import transaction

from django.utils.decorators import method_decorator
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count, Avg, F, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from openpyxl import Workbook

from .models import (
    Brand, Category, ComponentFamily, Currency, OverheadFactor, ProductAttributeDefinition, StorageBin,
    StorageLocation, Supplier, Location, Product, StockLevel,
    StockMovement, StockTake, StockTakeItem, PurchaseOrder,
    PurchaseOrderItem, ReorderAlert,
)
from .forms import (
    CategoryForm, CurrencyForm, ProductAttributeDefinitionForm, ProductBulkUpdateForm, SupplierForm, LocationForm, ProductForm, ProductSearchForm,
    StockAdjustmentForm, StockTransferForm, PurchaseOrderForm, StockTakeForm,
    AdvancedProductSearchForm, OverheadFactorForm
)
from .decorators import (
    inventory_permission_required, stock_adjustment_permission, location_access_required,
    purchase_order_permission, stock_take_permission, cost_data_access, bulk_operation_permission
)
from .utils import (
    ExportManager, InventoryAnalytics, PricingCalculator, calculate_available_stock, calculate_days_of_stock, get_low_stock_products, get_stock_status, calculate_stock_value,
    create_stock_movement, BarcodeManager
)

logger = logging.getLogger(__name__)

# =====================================
# BASE VIEW CLASSES FOR CONSISTENCY
# =====================================

class BaseInventoryMixin:
    """Common functionality for all inventory views"""
    
    def get_base_context(self, **extra_context):
        """Generate consistent base context"""
        context = {
            'app_name': 'inventory',
            'timestamp': timezone.now(),
        }
        context.update(extra_context)
        return context

class BaseInventoryListView(LoginRequiredMixin, ListView, BaseInventoryMixin):
    """Base class for inventory list views with consistent pagination and permissions"""
    paginate_by = 25
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.model._meta.verbose_name_plural.title()
        
        # Add summary statistics
        queryset = self.get_queryset()
        summary = {
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count() if hasattr(self.model, 'is_active') else None,
        }
        
        context.update(self.get_base_context(
            page_title=f'{model_name}',
            summary=summary,
        ))
        return context

class BaseInventoryCreateView(LoginRequiredMixin, CreateView, BaseInventoryMixin):
    """Base class for inventory create views with consistent permissions and messages"""
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.model._meta.verbose_name.title()
        
        context.update(self.get_base_context(
            page_title=f'Create {model_name}',
            form_action='Create',
        ))
        return context
    
    def form_valid(self, form):
        model_name = self.model._meta.verbose_name
        messages.success(
            self.request, 
            f'{model_name.title()} "{form.instance}" created successfully'
        )
        return super().form_valid(form)

class BaseInventoryUpdateView(LoginRequiredMixin, UpdateView, BaseInventoryMixin):
    """Base class for inventory update views with consistent permissions and messages"""
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.model._meta.verbose_name.title()
        
        context.update(self.get_base_context(
            page_title=f'Edit {model_name}: {self.object}',
            form_action='Update',
        ))
        return context
    
    def form_valid(self, form):
        model_name = self.model._meta.verbose_name
        messages.success(
            self.request, 
            f'{model_name.title()} "{form.instance}" updated successfully'
        )
        return super().form_valid(form)

class BaseInventoryDeleteView(LoginRequiredMixin, DeleteView, BaseInventoryMixin):
    """Base class for inventory delete views with consistent permissions"""
    
    @method_decorator(inventory_permission_required('admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.model._meta.verbose_name.title()
        
        context.update(self.get_base_context(
            page_title=f'Delete {model_name}',
        ))
        return context

class BaseInventoryDetailView(LoginRequiredMixin, DetailView, BaseInventoryMixin):
    """Base class for inventory detail views with consistent permissions"""
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = self.model._meta.verbose_name.title()
        
        context.update(self.get_base_context(
            page_title=f'{model_name}: {self.object}',
        ))
        return context

class BaseInventoryAjaxView(LoginRequiredMixin, View, BaseInventoryMixin):
    """Base class for AJAX inventory views"""
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def ajax_response(self, data, status=200):
        """Standardized AJAX response format"""
        return JsonResponse(data, status=status)
    
    def ajax_success(self, message="Success", **extra_data):
        """Standardized success response"""
        data = {'success': True, 'message': message}
        data.update(extra_data)
        return self.ajax_response(data)
    
    def ajax_error(self, message="Error occurred", status=400, **extra_data):
        """Standardized error response"""
        data = {'success': False, 'message': message}
        data.update(extra_data)
        return self.ajax_response(data, status=status)

# =====================================
# SPECIALIZED VIEW MIXINS
# =====================================

class ProductRelatedMixin:
    """Mixin for views that show products related to another entity"""
    
    def get_products_queryset(self):
        """Get optimized products queryset"""
        return Product.objects.select_related(
            'category', 'brand', 'supplier'
        ).filter(is_active=True)

class StockOperationMixin:
    """Mixin for views that perform stock operations"""
    
    @method_decorator(stock_adjustment_permission())
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def create_stock_movement(self, product, movement_type, quantity, **kwargs):
        """Helper to create stock movement records"""
        return create_stock_movement(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            user=self.request.user,
            **kwargs
        )

class BulkOperationMixin:
    """Mixin for bulk operation views"""
    
    @method_decorator(bulk_operation_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def process_bulk_operation(self, queryset, operation, **kwargs):
        """Process bulk operations with transaction safety"""
        try:
            with transaction.atomic():
                result = operation(queryset, **kwargs)
                return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Bulk operation failed: {str(e)}")
            return {'success': False, 'error': str(e)}

# =====================================
# PERMISSION MIXINS
# =====================================

class InventoryViewMixin:
    """Mixin for read-only inventory operations"""
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class InventoryEditMixin:
    """Mixin for inventory edit operations"""
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class InventoryAdminMixin:
    """Mixin for inventory admin operations"""
    
    @method_decorator(inventory_permission_required('admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

# =====================================
# DASHBOARD AND OVERVIEW VIEWS
# =====================================

@method_decorator(inventory_permission_required('view'), name='dispatch')
class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """Main inventory dashboard with comprehensive overview"""
    template_name = 'inventory/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Key metrics
        total_products = Product.objects.filter(is_active=True).count()
        total_stock_value = Product.objects.filter(is_active=True).aggregate(
            total=Sum(F('current_stock') * F('cost_price'))
        )['total'] or 0
        
        low_stock_products = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('reorder_level')
        ).count()
        
        out_of_stock_products = Product.objects.filter(
            is_active=True,
            current_stock=0
        ).count()
        
        # Recent movements
        recent_movements = StockMovement.objects.select_related('product').order_by('-created_at')[:10]
        
        # Top products by value
        top_products = Product.objects.filter(is_active=True).annotate(
            stock_value=F('current_stock') * F('cost_price')
        ).order_by('-stock_value')[:10]
        
        context.update({
            'page_title': 'Inventory Dashboard',
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'recent_movements': recent_movements,
            'top_products': top_products,
        })
        return context

class InventoryValuationReportView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/reports/inventory_valuation.html"

    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        import datetime
        from django.db.models import Sum, F, Count, Q
        from .models import Product, Category, Supplier, Location  # Import Location!
        context = super().get_context_data(**kwargs)

        # 1. Support filters from GET
        request = self.request
        as_of_date = request.GET.get('as_of_date') or datetime.date.today().isoformat()
        category_id = request.GET.get('category')
        location_id = request.GET.get('location')

        # 2. Base queryset: only active products
        products = Product.objects.filter(is_active=True)

        if category_id:
            products = products.filter(category_id=category_id)
        if location_id:
            # If you track stock by location via a StockLevel model, you would join here.
            # For now, just show all products, or implement as needed.
            pass

        # 3. Compute stats for products
        total_products = products.count()
        total_quantity = products.aggregate(total=Sum('current_stock'))['total'] or 0
        total_value = products.aggregate(
            value=Sum(F('current_stock') * F('cost_price'))
        )['value'] or 0
        avg_margin = products.aggregate(
            avg=Sum(
                F('selling_price') - F('cost_price')
            ) / Count('id')
        )['avg'] or 0

        # 4. Category breakdown for charts
        categories = Category.objects.filter(is_active=True).annotate(
            total_quantity=Sum('products__current_stock', filter=Q(products__is_active=True)),
            total_value=Sum(F('products__current_stock') * F('products__cost_price'), filter=Q(products__is_active=True)),
            product_count=Count('products', filter=Q(products__is_active=True)),
        ).order_by('-total_value')

        total_value_all = categories.aggregate(tot=Sum('total_value'))['tot'] or 1  # avoid divide by zero

        category_list = []
        for cat in categories:
            if not cat.total_value:
                continue
            percent = (cat.total_value / total_value_all) * 100 if total_value_all else 0
            category_list.append({
                'id': cat.id,
                'name': cat.name,
                'total_quantity': cat.total_quantity or 0,
                'total_value': cat.total_value or 0,
                'product_count': cat.product_count or 0,
                'percentage': percent,
            })

        # 5. Detailed product list for table
        product_list = []
        for p in products.select_related('category', 'supplier'):
            margin = (p.selling_price - p.cost_price) if p.cost_price else 0
            margin_pct = ((p.selling_price - p.cost_price) / p.cost_price * 100) if p.cost_price else 0
            product_list.append({
                'id': p.id,
                'sku': p.sku,
                'name': p.name,
                'category': p.category.name if p.category else '',
                'supplier': p.supplier.name if p.supplier else '',
                'quantity': p.current_stock,
                'cost_price': p.cost_price,
                'selling_price': p.selling_price,
                'total_value': (p.current_stock * p.cost_price) if p.current_stock else 0,
                'margin_amount': margin,
                'margin_percentage': margin_pct,
                'stock_status': p.stock_status,
            })

        # 6. Other context for filters
        all_categories = Category.objects.filter(is_active=True)
        all_locations = Location.objects.filter(is_active=True)

        # 7. Provide 'today' for the date picker default
        today = datetime.date.today().isoformat()

        context.update({
            "today": today,
            "categories": all_categories,
            "locations": all_locations,
            "report_data": {
                "as_of_date": as_of_date,
                "total_products": total_products,
                "total_quantity": total_quantity,
                "total_value": total_value,
                "avg_margin": avg_margin,
                "categories": category_list,
                "products": product_list,
                "location": all_locations.get(id=location_id).name if location_id else "All Locations",
            },
            "last_updated": datetime.datetime.now(),
        })
        return context

class InventoryOverviewView(LoginRequiredMixin, TemplateView):
    """Comprehensive inventory overview"""
    template_name = 'inventory/overview.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Category breakdown
        category_stats = Category.objects.filter(is_active=True).annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            stock_value=Sum(
                F('products__current_stock') * F('products__cost_price'),
                filter=Q(products__is_active=True)
            )
        ).order_by('-stock_value')
        
        # Supplier breakdown
        supplier_stats = Supplier.objects.filter(is_active=True).annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            stock_value=Sum(
                F('products__current_stock') * F('products__cost_price'),
                filter=Q(products__is_active=True)
            )
        ).order_by('-stock_value')[:10]
        
        context.update({
            'page_title': 'Inventory Overview',
            'category_stats': category_stats,
            'supplier_stats': supplier_stats,
        })
        return context

@login_required
@inventory_permission_required('view')
def inventory_alerts_view(request):
    """View for managing inventory alerts and notifications"""
    template_name = 'inventory/alerts.html'
    
    # Get active alerts
    reorder_alerts = ReorderAlert.objects.filter(
        status__in=['active', 'acknowledged']
    ).select_related('product', 'suggested_supplier').order_by('priority', '-created_at')
    
    # Get low stock products
    low_stock_products = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level')
    ).select_related('category', 'supplier').order_by('current_stock')
    
    # Get overdue purchase orders
    overdue_pos = PurchaseOrder.objects.filter(
        status__in=['sent', 'acknowledged'],
        expected_delivery_date__lt=timezone.now().date()
    ).select_related('supplier')
    
    context = {
        'reorder_alerts': reorder_alerts,
        'low_stock_products': low_stock_products,
        'overdue_pos': overdue_pos,
        'alert_count': reorder_alerts.count(),
        'low_stock_count': low_stock_products.count(),
        'overdue_po_count': overdue_pos.count()
    }
    
    return render(request, template_name, context)

# =====================================
# PRODUCT MANAGEMENT VIEWS
# =====================================

class ProductListView(BaseInventoryListView):
    """List all products with search and filtering"""
    model = Product
    template_name = 'inventory/products/product_list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Product.objects.select_related(
            'category', 'brand', 'supplier'
        ).filter(is_active=True)
        
        # Apply search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Apply category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Apply supplier filter
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        return queryset.order_by('name')

class ProductDetailView(BaseInventoryDetailView):
    """Product detail view with stock levels and movements"""
    model = Product
    template_name = 'inventory/products/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        product = context['product']
        
        # Get stock levels by location
        stock_levels = product.stock_levels.select_related('location').all()
        
        # Get recent movements
        recent_movements = product.movements.select_related(
            'from_location', 'to_location'
        ).order_by('-created_at')[:20]
        
        # Calculate total cost including overheads
        total_cost = PricingCalculator.calculate_product_total_cost(product)
        
        context.update({
            'stock_levels': stock_levels,
            'recent_movements': recent_movements,
            'total_cost': total_cost,
            'stock_status': get_stock_status(product),
        })
        return context

class ProductCreateView(BaseInventoryCreateView):
    """Create new product"""
    model = Product
    form_class = ProductForm
    template_name = 'inventory/products/product_form.html'
    success_url = reverse_lazy('inventory:product_list')

class ProductUpdateView(BaseInventoryUpdateView):
    """Update existing product"""
    model = Product
    form_class = ProductForm
    template_name = 'inventory/products/product_form.html'
    success_url = reverse_lazy('inventory:product_list')

class ProductDeleteView(BaseInventoryDeleteView):
    """Delete product (admin only)"""
    model = Product
    template_name = 'inventory/products/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')

class ProductSearchView(BaseInventoryListView):
    """Advanced product search"""
    model = Product
    template_name = 'inventory/products/product_search.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        form = ProductSearchForm(self.request.GET)
        queryset = Product.objects.select_related(
            'category', 'brand', 'supplier'
        ).filter(is_active=True)
        
        if form.is_valid():
            if form.cleaned_data.get('search'):
                search = form.cleaned_data['search']
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(sku__icontains=search) |
                    Q(barcode__icontains=search)
                )
            
            if form.cleaned_data.get('category'):
                queryset = queryset.filter(category=form.cleaned_data['category'])
            
            if form.cleaned_data.get('supplier'):
                queryset = queryset.filter(supplier=form.cleaned_data['supplier'])
            
            if form.cleaned_data.get('stock_status'):
                status = form.cleaned_data['stock_status']
                if status == 'in_stock':
                    queryset = queryset.filter(current_stock__gt=F('reorder_level'))
                elif status == 'low_stock':
                    queryset = queryset.filter(
                        current_stock__lte=F('reorder_level'),
                        current_stock__gt=0
                    )
                elif status == 'out_of_stock':
                    queryset = queryset.filter(current_stock=0)
            
            min_price = form.cleaned_data.get('min_price')
            max_price = form.cleaned_data.get('max_price')
            if min_price:
                queryset = queryset.filter(selling_price__gte=min_price)
            if max_price:
                queryset = queryset.filter(selling_price__lte=max_price)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ProductSearchForm(self.request.GET)
        return context

class ProductAdvancedSearchView(ProductSearchView):
    """Advanced product search with more filters"""
    template_name = 'inventory/products/product_advanced_search.html'

class ProductBulkCreateView(LoginRequiredMixin, TemplateView, BulkOperationMixin):
    """Bulk product creation"""
    template_name = 'inventory/products/product_bulk_create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Bulk Product Creation'
        return context

class ProductBulkImportView(LoginRequiredMixin, TemplateView):
    """Bulk product import from CSV/Excel"""
    template_name = 'inventory/products/product_bulk_import.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Bulk Product Import'
        return context

class ProductAttributeListView(BaseInventoryListView):
    """List product attributes"""
    model = ProductAttributeDefinition
    template_name = 'inventory/configuration/product_attribute_list.html'
    context_object_name = 'attributes'

class ProductAttributeCreateView(BaseInventoryCreateView):
    """Create product attribute"""
    model = ProductAttributeDefinition
    form_class = ProductAttributeDefinitionForm
    template_name = 'inventory/configuration/product_attribute_form.html'
    success_url = reverse_lazy('inventory:product_attribute_list')

class ProductAttributeUpdateView(BaseInventoryUpdateView):
    """Update product attribute"""
    model = ProductAttributeDefinition
    form_class = ProductAttributeDefinitionForm
    template_name = 'inventory/configuration/product_attribute_form.html'
    success_url = reverse_lazy('inventory:product_attribute_list')

class ProductAttributeDeleteView(BaseInventoryDeleteView):
    """Delete product attribute"""
    model = ProductAttributeDefinition
    template_name = 'inventory/configuration/product_attribute_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_attribute_list')

class OverheadFactorListView(BaseInventoryListView):
    """List overhead factors"""
    model = OverheadFactor
    template_name = 'inventory/configuration/overhead_factor_list.html'
    context_object_name = 'overhead_factors'

class OverheadFactorCreateView(BaseInventoryCreateView):
    """Create overhead factor"""
    model = OverheadFactor
    form_class = OverheadFactorForm
    template_name = 'inventory/configuration/overhead_factor_form.html'
    success_url = reverse_lazy('inventory:overhead_factor_list')

class OverheadFactorUpdateView(BaseInventoryUpdateView):
    """Update overhead factor"""
    model = OverheadFactor
    form_class = OverheadFactorForm
    template_name = 'inventory/configuration/overhead_factor_form.html'
    success_url = reverse_lazy('inventory:overhead_factor_list')

class OverheadFactorDeleteView(BaseInventoryDeleteView):
    """Delete overhead factor"""
    model = OverheadFactor
    template_name = 'inventory/configuration/overhead_factor_confirm_delete.html'
    success_url = reverse_lazy('inventory:overhead_factor_list')


def product_import_template_csv(request):
    """Generate CSV import template"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_import_template.csv"'
    
    writer = csv.writer(response)
    
    # Headers
    writer.writerow([
        'sku', 'name', 'description', 'category', 'supplier', 'brand',
        'cost_price', 'selling_price', 'current_stock', 'reorder_level',
        'economic_order_quantity', 'barcode', 'is_active'
    ])
    
    # Sample data
    writer.writerow([
        'BT-2024-001', 'Sample Electronic Component', 'Sample description',
        'Electronics', 'ABC Supplier', 'Generic Brand',
        '10.00', '15.00', '100', '10', '50', '1234567890', 'True'
    ])
    
    writer.writerow([
        'BT-2024-002', 'Another Component', 'Another description',
        'Components', 'XYZ Supplier', 'Premium Brand',
        '25.50', '40.00', '50', '5', '25', '0987654321', 'True'
    ])
    
    return response


@login_required
@inventory_permission_required('edit')
def adjust_stock_view(self, request, pk):
    """
    Stock adjustment view for individual products.
    
    Allows authorized users to adjust stock levels with proper audit trail.
    """
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                product = form.cleaned_data['product']
                quantity = int(form.cleaned_data['quantity'])
                adjustment_type = form.cleaned_data['adjustment_type']  # 'set' | 'add' | 'subtract'
                location = form.cleaned_data.get('location')
                reason = form.cleaned_data.get('reason', '')
                notes = form.cleaned_data.get('notes', '')
                
                if location:
                    stock_level, _ = StockLevel.objects.get_or_create(
                        product=product,
                        location=location,
                        defaults={'quantity': 0}
                    )
                    previous_stock = stock_level.quantity
                else:
                    previous_stock = product.current_stock
                
                # Calculate actual adjustment quantity
                if adjustment_type == 'set':
                    new_stock = quantity
                    actual_adjustment = new_stock - previous_stock
                elif adjustment_type == 'add':
                    new_stock = previous_stock + quantity
                    actual_adjustment = quantity
                else:  # 'subtract'
                    new_stock = max(0, previous_stock - quantity)
                    actual_adjustment = -(previous_stock - new_stock)
                
                if location:
                    stock_level.quantity = new_stock
                    stock_level.save()
                else:
                    product.current_stock = new_stock
                    product.save()
                    
                # Check for negative stock
                if product.current_stock + actual_adjustment < 0:
                    messages.error(
                        request,
                        f'Cannot adjust stock to negative value. Current stock: {product.current_stock}'
                    )
                    return render(request, 'inventory/product/adjust_stock.html', {
                        'product': product,
                        'form': form
                    })
                
                # Create stock movement
                StockMovement.objects.create(
                    product=product,
                    movement_type='adjustment',
                    quantity=actual_adjustment,
                    from_location=location if actual_adjustment < 0 else None,
                    to_location=location if actual_adjustment > 0 else None,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference=f"ADJ-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    notes=f"Reason: {reason}. {notes}",
                    created_by=self.request.user
                )

                messages.success(self.request, f"Stock adjusted for {product.name}: {previous_stock} → {new_stock}")
                
                logger.info(
                    f"Stock adjustment: {actual_adjustment} units of {product.sku} "
                    f"by {request.user.username}. Reason: {reason}"
                )
                
                return redirect('inventory:product_detail', pk=product.pk)
                
            except Exception as e:
                logger.error(f"Error adjusting stock: {str(e)}")
                messages.error(request, f'Error adjusting stock: {str(e)}')
        
    else:
        form = StockAdjustmentForm(initial={'product': product}, user=request.user)
    
    context = {
        'product': product,
        'form': form,
        'stock_levels': StockLevel.objects.filter(product=product).select_related('location')
    }
    
    return render(request, 'inventory/product/adjust_stock.html', context)

@login_required
@inventory_permission_required('edit')
def product_import_view(request):
    """
    Product bulk import page (shows the wizard and handles CSV upload).
    If you want to support AJAX/Excel/validation steps, extend this!
    """
    if request.method == "POST" and request.FILES.get('import_file'):
        csv_file = request.FILES['import_file']
        try:
            decoded = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded)
            created, updated = 0, 0
            for row in reader:
                sku = row.get('sku') or row.get('SKU')
                name = row.get('name') or row.get('Name')
                if not sku or not name:
                    continue
                product, created_flag = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'name': name,
                        'cost_price': row.get('cost_price', 0),
                        'selling_price': row.get('selling_price', 0),
                        # Extend for more fields as needed!
                        'created_by': request.user,
                        'is_active': True,
                    }
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
            messages.success(request, f'Imported {created} new products, updated {updated}.')
            return redirect('inventory:product_list')
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")

    return render(request, "inventory/product/product_import.html", {})

@login_required
@inventory_permission_required('view')
def product_import_template_excel(request):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Product Import Template"

    headers = [
        'sku', 'name', 'category', 'supplier', 'description', 'cost_price',
        'selling_price', 'current_stock', 'reorder_level', 'barcode', 'brand'
    ]
    sheet.append(headers)
    sheet.append([
        'BT-2024-001', 'Sample Product', 'Electronics', 'ABC Supplier', 'Sample desc',
        '10.00', '15.00', '100', '10', '0123456789012', 'Generic'
    ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=product_import_template.xlsx'
    workbook.save(response)
    return response

@login_required
@inventory_permission_required('view')
def export_data_view(request):
    # Export all products as CSV for now
    products = Product.objects.filter(is_active=True).select_related('category', 'supplier')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_products.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Name', 'Category', 'Supplier', 'Cost Price', 'Selling Price', 'Stock', 'Barcode', 'Is Active'
    ])
    for p in products:
        writer.writerow([
            p.sku, p.name, p.category.name if p.category else '', p.supplier.name if p.supplier else '',
            p.cost_price, p.selling_price, p.current_stock, p.barcode, p.is_active
        ])
    return response

@login_required
@inventory_permission_required('view')
def product_details_api(request, product_id):
    """
    API endpoint: Get detailed product information including stock levels.
    Used for quote system integration and mobile apps.
    """
    try:
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Get stock levels by location
        stock_levels = []
        for stock_level in product.stock_levels.select_related('location'):
            stock_levels.append({
                'location_id': stock_level.location.id,
                'location_name': stock_level.location.name,
                'quantity': stock_level.quantity,
                'available_quantity': stock_level.available_quantity,
                'reserved_quantity': stock_level.reserved_quantity,
                'last_counted': stock_level.last_counted.isoformat() if stock_level.last_counted else None,
            })
        
        # Calculate total cost including overheads
        overhead_factors = OverheadFactor.objects.filter(is_active=True)
        total_overhead_rate = sum(factor.percentage for factor in overhead_factors)
        total_cost = product.cost_price * (1 + total_overhead_rate / 100)
        
        # Get recent movements
        recent_movements = []
        for movement in product.stock_movements.select_related('from_location', 'to_location')[:10]:
            recent_movements.append({
                'date': movement.created_at.isoformat(),
                'type': movement.movement_type,
                'quantity': movement.quantity,
                'reference': movement.reference,
                'from_location': movement.from_location.name if movement.from_location else None,
                'to_location': movement.to_location.name if movement.to_location else None,
            })
        
        data = {
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name
            } if product.category else None,
            'supplier': {
                'id': product.supplier.id,
                'name': product.supplier.name,
                'currency': product.supplier.currency,
                'lead_time_days': product.supplier.average_lead_time_days,
            } if product.supplier else None,
            'brand': {
                'id': product.brand.id,
                'name': product.brand.name
            } if product.brand else None,
            'pricing': {
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'total_cost_with_overhead': float(total_cost),
                'margin': float(product.selling_price - total_cost),
                'margin_percent': float((product.selling_price - total_cost) / product.selling_price * 100) if product.selling_price > 0 else 0,
            },
            'stock': {
                'current_stock': product.current_stock,
                'reorder_level': product.reorder_level,
                'economic_order_quantity': product.economic_order_quantity,
                'last_restocked': product.last_restocked_date.isoformat() if product.last_restocked_date else None,
                'stock_status': get_stock_status(product),
                'stock_levels_by_location': stock_levels,
            },
            'barcode': product.barcode,
            'is_active': product.is_active,
            'created_at': product.created_at.isoformat(),
            'recent_movements': recent_movements,
        }
        
        return JsonResponse({'success': True, 'product': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# =====================================
# COMPONENT FAMILY MANAGEMENT VIEWS
# =====================================

class ComponentFamilyListView(BaseInventoryListView):
    model = ComponentFamily
    template_name = "inventory/configuration/component_family_list.html"
    context_object_name = "families"

class ComponentFamilyCreateView(BaseInventoryCreateView):
    model = ComponentFamily
    fields = [
        "name", "slug", "description", "default_attributes",
        "typical_markup_percentage", "default_bin_prefix",
        "is_active", "display_order",
    ]
    template_name = "inventory/configuration/component_family_form.html"
    success_url = reverse_lazy("inventory:component_family_list")

class ComponentFamilyUpdateView(BaseInventoryUpdateView):
    model = ComponentFamily
    fields = [
        "name", "slug", "description", "default_attributes",
        "typical_markup_percentage", "default_bin_prefix",
        "is_active", "display_order",
    ]
    template_name = "inventory/configuration/component_family_form.html"
    success_url = reverse_lazy("inventory:component_family_list")

class ComponentFamilyDeleteView(BaseInventoryDeleteView):
    model = ComponentFamily
    template_name = "inventory/confirm_delete.html"
    success_url = reverse_lazy("inventory:component_family_list")

class ComponentFamilyDetailView(BaseInventoryDetailView):
    model = ComponentFamily
    template_name = "inventory/configuration/component_family_detail.html"
    context_object_name = "family"

# =====================================
# STOCK MANAGEMENT VIEWS
# =====================================

class StockAdjustmentView(LoginRequiredMixin, TemplateView, StockOperationMixin):
    """Stock adjustment interface"""
    template_name = 'inventory/stock/stock_adjustment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'page_title': 'Stock Adjustment',
            'form': StockAdjustmentForm(),
            'products': Product.objects.filter(is_active=True).select_related('category')[:100]
        })
        return context
    
    def post(self, request, *args, **kwargs):
        form = StockAdjustmentForm(request.POST)
        
        if form.is_valid():
            try:
                product_id = request.POST.get('product_id')
                product = get_object_or_404(Product, id=product_id)
                
                adjustment_type = form.cleaned_data['adjustment_type']
                quantity = form.cleaned_data['quantity']
                reason = form.cleaned_data['reason']
                
                # Validate stock movement
                if adjustment_type == 'decrease':
                    is_valid, error_msg = validate_stock_movement(product, 'decrease', quantity)
                    if not is_valid:
                        messages.error(request, error_msg)
                        return redirect('inventory:stock_adjustment')
                
                # Perform adjustment
                if adjustment_type == 'increase':
                    product.current_stock += quantity
                elif adjustment_type == 'decrease':
                    product.current_stock -= quantity
                elif adjustment_type == 'set_to':
                    product.current_stock = quantity
                
                product.save()
                
                # Create movement record
                self.create_stock_movement(
                    product=product,
                    movement_type=adjustment_type,
                    quantity=quantity,
                    reason=reason
                )
                
                messages.success(
                    request, 
                    f'Stock adjusted for {product.name}. New stock level: {product.current_stock}'
                )
                
            except Exception as e:
                messages.error(request, f'Stock adjustment failed: {str(e)}')
        
        return redirect('inventory:stock_adjustment')

class StockTransferView(LoginRequiredMixin, TemplateView, StockOperationMixin):
    """Stock transfer between locations"""
    template_name = 'inventory/stock/stock_transfer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'page_title': 'Stock Transfer',
            'form': StockTransferForm(),
            'locations': Location.objects.filter(is_active=True),
        })
        return context

class BulkStockAdjustmentView(LoginRequiredMixin, TemplateView, BulkOperationMixin):
    """Bulk stock adjustments"""
    template_name = 'inventory/stock/bulk_stock_adjustment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'page_title': 'Bulk Stock Adjustment',
        })
        return context

class StockMovementListView(BaseInventoryListView):
    """List stock movements"""
    model = StockMovement
    template_name = 'inventory/stock/stock_movement_list.html'
    context_object_name = 'movements'
    
    def get_queryset(self):
        return StockMovement.objects.select_related(
            'product', 'from_location', 'to_location', 'user'
        ).order_by('-created_at')

class StockOverviewView(LoginRequiredMixin, TemplateView):
    """
    Complete stock overview across all locations and products.
    Shows current stock levels, values, and alerts.
    """
    template_name = 'inventory/stock/stock_overview.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all stock levels with related data
        stock_levels = StockLevel.objects.select_related(
            'product', 'location'
        ).filter(quantity__gt=0)
        
        # Calculate summary metrics
        total_products = Product.objects.filter(is_active=True).count()
        total_stock_value = sum(sl.stock_value for sl in stock_levels)
        low_stock_count = Product.objects.filter(
            current_stock__lte=F('reorder_level'),
            is_active=True
        ).count()
        out_of_stock_count = Product.objects.filter(
            current_stock=0,
            is_active=True
        ).count()
        
        # Get stock by location
        locations = Location.objects.filter(is_active=True)
        stock_by_location = []
        for location in locations:
            location_stock = stock_levels.filter(location=location)
            location_value = sum(sl.stock_value for sl in location_stock)
            stock_by_location.append({
                'location': location,
                'product_count': location_stock.count(),
                'total_value': location_value,
                'stock_levels': location_stock[:10]  # Show top 10
            })
        
        # Get recent movements
        recent_movements = StockMovement.objects.select_related(
            'product', 'from_location', 'to_location'
        ).order_by('-created_at')[:20]
        
        context.update({
            'page_title': 'Stock Overview',
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'stock_by_location': stock_by_location,
            'recent_movements': recent_movements,
            'locations': locations,
        })
        return context

class StockByLocationView(LoginRequiredMixin, DetailView):
    """
    Detailed view of stock at a specific location.
    """
    model = Location
    template_name = 'inventory/stock/stock_by_location.html'
    context_object_name = 'location'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.get_object()
        
        # Get stock levels for this location
        stock_levels = StockLevel.objects.filter(
            location=location
        ).select_related('product', 'product__category', 'product__supplier')
        
        # Calculate metrics
        total_value = sum(sl.stock_value for sl in stock_levels)
        total_products = stock_levels.count()
        
        context.update({
            'page_title': f'Stock at {location.name}',
            'stock_levels': stock_levels,
            'total_value': total_value,
            'total_products': total_products,
        })
        return context

class StockAdjustDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/stock/stock_adjust_dashboard.html"

    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = Product.objects.filter(is_active=True)
        categories = Category.objects.filter(is_active=True)
        locations = Location.objects.filter(is_active=True)

        # You could also support filtering here (e.g., by GET params)

        context.update({
            "products": products,
            "categories": categories,
            "locations": locations,
            "stock_adjustment_form": StockAdjustmentForm(),
        })
        return context

class LowStockReportView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/stock/low_stock.html"

    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        low_stock_products = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('reorder_level'),
            current_stock__gt=0
        ).select_related('category', 'supplier').order_by('current_stock')
        context['low_stock_products'] = low_stock_products
        return context

class StockLevelListView(LoginRequiredMixin, ListView):
    """List stock levels across locations"""
    model = StockLevel
    template_name = 'inventory/stock/stock_level_list.html'
    context_object_name = 'stock_levels'
    paginate_by = 50
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        return StockLevel.objects.select_related(
            'product', 'location'
        ).filter(product__is_active=True).order_by('product__name')

class ReorderAlertListView(BaseInventoryListView):
    """List reorder alerts"""
    model = ReorderAlert
    template_name = 'inventory/reorder/reorder_alert_list.html'
    context_object_name = 'alerts'
    
    def get_queryset(self):
        return ReorderAlert.objects.select_related(
            'product', 'supplier'
        ).filter(is_active=True).order_by('-created_at')

class LowStockOrderingView(LoginRequiredMixin, TemplateView):
    """Low stock ordering interface"""
    template_name = 'inventory/reorder/low_stock_ordering.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get low stock products
        low_stock_products = get_low_stock_products()
        
        # Generate reorder recommendations
        recommendations = InventoryAnalytics.generate_reorder_recommendations()
        
        context.update({
            'page_title': 'Low Stock Ordering',
            'low_stock_products': low_stock_products,
            'recommendations': recommendations,
        })
        return context

@login_required
@stock_adjustment_permission
def stock_adjustment_view(request):
    """Adjust stock levels"""
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            # Process stock adjustment
            adjustment = form.save(commit=False)
            adjustment.adjusted_by = request.user
            adjustment.save()
            
            # Create stock movement record
            create_stock_movement(
                product=adjustment.product,
                movement_type='adjustment',
                quantity=adjustment.adjustment_quantity,
                user=request.user,
                notes=adjustment.notes
            )
            
            messages.success(request, 'Stock adjustment completed successfully')
            return redirect('inventory:stock_level_list')
    else:
        form = StockAdjustmentForm()
    
    context = {
        'page_title': 'Stock Adjustment',
        'form': form,
    }
    return render(request, 'inventory/stock/stock_adjustment.html', context)

@login_required
@inventory_permission_required('view_stocktake')
def export_stock_take_pdf(request, pk):
    stock_take = StockTake.objects.get(pk=pk)
    html_string = render_to_string('inventory/stock_take_pdf.html', {'stock_take': stock_take})
    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="stock_take_{stock_take.reference}.pdf"'
    return response

@login_required
@inventory_permission_required('view_stocktake')
def export_stock_take_excel(request, pk):
    stock_take = StockTake.objects.get(pk=pk)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"Stock Take {stock_take.reference}"

    sheet.append(["SKU", "Product", "Expected", "Counted", "Variance", "Location", "Status"])
    for item in stock_take.items.select_related('product', 'location'):
        sheet.append([
            item.product.sku,
            item.product.name,
            item.expected_quantity,
            item.counted_quantity,
            item.variance,
            item.location.name if item.location else "N/A",
            item.status,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"stock_take_{stock_take.reference}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response

@login_required
def get_live_stock(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({'sku': product.sku, 'name': product.name, 'current_stock': product.current_stock})
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

@login_required
@inventory_permission_required('edit')
def stock_transfer_view(request):
    """Stock transfer between locations"""
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        
        if form.is_valid():
            try:
                from .utils import transfer_stock_between_locations
                
                product = form.cleaned_data['product']
                from_location = form.cleaned_data['from_location']
                to_location = form.cleaned_data['to_location']
                quantity = form.cleaned_data['quantity']
                reference = form.cleaned_data['reference']
                notes = form.cleaned_data['notes']
                
                # Perform transfer
                outgoing, incoming = transfer_stock_between_locations(
                    product=product,
                    from_location=from_location,
                    to_location=to_location,
                    quantity=quantity,
                    reference=reference,
                    user=request.user,
                    notes=notes
                )
                
                messages.success(
                    request,
                    f'Successfully transferred {quantity} units of {product.name} '
                    f'from {from_location.name} to {to_location.name}'
                )
                
                logger.info(
                    f"Stock transfer: {quantity} units of {product.sku} "
                    f"from {from_location.name} to {to_location.name} "
                    f"by {request.user.username}"
                )
                
                return redirect('inventory:stock_overview')
                
            except Exception as e:
                logger.error(f"Error in stock transfer: {str(e)}")
                messages.error(request, f'Transfer failed: {str(e)}')
    else:
        form = StockTransferForm()
    
    context = {
        'form': form,
        'page_title': 'Stock Transfer'
    }
    
    return render(request, 'inventory/stock/stock_transfer.html', context)

@login_required
@inventory_permission_required('view')
def low_stock_view(request):
    """
    List all products that are low in stock (current_stock <= reorder_level and > 0).
    """
    low_stock_products = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level'),
        current_stock__gt=0
    ).select_related('category', 'supplier').order_by('current_stock')

    context = {
        "page_title": "Low Stock Products",
        "low_stock_products": low_stock_products,
    }
    return render(request, "inventory/stock/low_stock.html", context)

@login_required
@inventory_permission_required('edit')
def stock_take_create(request):
    """
    Schedule a new stock take.
    """
    if request.method == "POST":
        form = StockTakeForm(request.POST)
        if form.is_valid():
            stock_take = form.save(commit=False)
            stock_take.created_by = request.user
            stock_take.status = 'planned'
            stock_take.save()
            messages.success(request, "Stock take scheduled successfully.")
            return redirect('inventory:stock_take_detail', pk=stock_take.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StockTakeForm()

    context = {
        "form": form,
        "stock_take": None,  # So your template shows the creation form
    }
    return render(request, "inventory/stock/stock_take.html", context)

@login_required
@inventory_permission_required('view')
def reorder_alert_list(request):
    """
    List all active and recent reorder alerts.
    """
    alerts = ReorderAlert.objects.select_related('product', 'suggested_supplier').order_by(
        '-priority', '-created_at'
    )
    context = {
        "page_title": "Reorder Alerts",
        "alerts": alerts,
    }
    return render(request, "inventory/alerts/reorder_alert_list.html", context)

@login_required
@inventory_permission_required('view')
def low_stock_report(request):
    """Generate low stock report"""
    products = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level')
    ).select_related('category', 'supplier').order_by('current_stock')
    
    context = {
        'page_title': 'Low Stock Report',
        'products': products,
        'total_products': products.count(),
    }
    
    return render(request, 'inventory/reports/low_stock_report.html', context)


# =====================================
# PURCHASE ORDER VIEWS
# =====================================

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    """List all purchase orders"""
    model = PurchaseOrder
    template_name = 'inventory/purchase_orders/po_list.html'
    context_object_name = 'purchase_orders'
    paginate_by = 25
    
    @method_decorator(purchase_order_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier').order_by('-created_at')

class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of purchase order"""
    model = PurchaseOrder
    template_name = 'inventory/purchase_orders/po_detail.html'
    context_object_name = 'purchase_order'
    
    @method_decorator(purchase_order_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        po = self.get_object()
        context.update({
            'page_title': f'Purchase Order: {po.po_number}',
            'po_items': po.items.select_related('product').all(),
            'total_value': sum(item.total_price for item in po.items.all()),
        })
        return context

class PurchaseOrderCreateView(LoginRequiredMixin, CreateView):
    """Create new purchase order"""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/purchase_orders/po_form.html'
    
    @method_decorator(purchase_order_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Purchase order {form.instance.po_number} created successfully')
        return super().form_valid(form)

class PurchaseOrderUpdateView(LoginRequiredMixin, UpdateView):
    """Update purchase order"""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory/purchase_orders/po_form.html'
    
    @method_decorator(purchase_order_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@login_required
@purchase_order_permission
def purchase_order_receive_view(request, pk):
    """Receive items from purchase order"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if request.method == 'POST':
        # Process receiving logic here
        po.status = 'received'
        po.received_date = timezone.now().date()
        po.save()
        
        messages.success(request, f'Purchase order {po.po_number} marked as received')
        return redirect('inventory:po_detail', pk=po.pk)
    
    context = {
        'page_title': f'Receive PO: {po.po_number}',
        'purchase_order': po,
        'po_items': po.items.select_related('product').all(),
    }
    return render(request, 'inventory/purchase_orders/po_receive.html', context)

@login_required
@purchase_order_permission
def purchase_order_cancel_view(request, pk):
    """Cancel purchase order"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if request.method == 'POST':
        po.status = 'cancelled'
        po.save()
        
        messages.success(request, f'Purchase order {po.po_number} cancelled')
        return redirect('inventory:po_list')
    
    context = {
        'page_title': f'Cancel PO: {po.po_number}',
        'purchase_order': po,
    }
    return render(request, 'inventory/purchase_orders/po_cancel.html', context)

# =====================================
# PRICING VIEWS
# =====================================

class CostCalculatorView(LoginRequiredMixin, TemplateView):
    """Calculate product costs with overhead factors"""
    template_name = 'inventory/pricing/cost_calculator.html'
    
    @method_decorator(cost_data_access)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get overhead factors for calculation
        overhead_factors = OverheadFactor.objects.filter(is_active=True)
        
        context.update({
            'page_title': 'Cost Calculator',
            'overhead_factors': overhead_factors,
        })
        return context

class BulkPriceUpdateView(LoginRequiredMixin, TemplateView):
    """Bulk update product prices"""
    template_name = 'inventory/pricing/bulk_price_update.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        # Process bulk price update
        price_adjustment = request.POST.get('price_adjustment', '0')
        adjustment_type = request.POST.get('adjustment_type', 'percentage')
        
        try:
            adjustment = Decimal(price_adjustment)
            updated_count = 0
            
            products = Product.objects.filter(is_active=True)
            for product in products:
                if adjustment_type == 'percentage':
                    product.selling_price *= (1 + adjustment / 100)
                else:
                    product.selling_price += adjustment
                product.save()
                updated_count += 1
            
            messages.success(request, f'Updated prices for {updated_count} products')
        except Exception as e:
            messages.error(request, f'Price update failed: {str(e)}')
        
        return redirect('inventory:product_list')

class MarginAnalysisView(LoginRequiredMixin, TemplateView):
    """Analyze profit margins across products"""
    template_name = 'inventory/pricing/margin_analysis.html'
    
    @method_decorator(cost_data_access)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate margin statistics
        products = Product.objects.filter(is_active=True).select_related('category')
        
        margin_stats = []
        for product in products:
            if product.selling_price > 0:
                margin = product.selling_price - product.cost_price
                margin_percentage = (margin / product.selling_price) * 100
                margin_stats.append({
                    'product': product,
                    'margin': margin,
                    'margin_percentage': margin_percentage,
                })
        
        # Sort by margin percentage
        margin_stats.sort(key=lambda x: x['margin_percentage'], reverse=True)
        
        context.update({
            'page_title': 'Margin Analysis',
            'margin_stats': margin_stats,
        })
        return context

class CompetitivePricingView(LoginRequiredMixin, TemplateView):
    """Compare pricing with competitors"""
    template_name = 'inventory/pricing/competitive_pricing.html'
    
    @method_decorator(cost_data_access)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Competitive Pricing Analysis',
        })
        return context

class MarkupRuleListView(LoginRequiredMixin, TemplateView):
    """List markup rules"""
    template_name = 'inventory/pricing/markup_rules.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class MarkupRuleCreateView(LoginRequiredMixin, TemplateView):
    """Create new markup rule"""
    template_name = 'inventory/pricing/markup_rule_form.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class OverheadAnalysisView(LoginRequiredMixin, TemplateView):
    """Analyze overhead costs"""
    template_name = 'inventory/pricing/overhead_analysis.html'
    
    @method_decorator(cost_data_access)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        overhead_factors = OverheadFactor.objects.filter(is_active=True)
        
        context.update({
            'page_title': 'Overhead Cost Analysis',
            'overhead_factors': overhead_factors,
        })
        return context

# =====================================
# LOCATION MANAGEMENT VIEWS  
# =====================================

class LocationListView(BaseInventoryListView):
    model = Location
    template_name = 'inventory/configuration/location_list.html'
    context_object_name = 'locations'

class LocationCreateView(BaseInventoryCreateView):
    model = Location
    form_class = LocationForm
    template_name = 'inventory/configuration/location_form.html'
    success_url = reverse_lazy('inventory:location_list')

class LocationUpdateView(BaseInventoryUpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'inventory/configuration/location_form.html'
    success_url = reverse_lazy('inventory:location_list')

class LocationDeleteView(BaseInventoryDeleteView):
    model = Location
    template_name = 'inventory/configuration/location_confirm_delete.html'
    success_url = reverse_lazy('inventory:location_list')

class LocationDetailView(BaseInventoryDetailView):
    model = Location
    template_name = 'inventory/configuration/location_detail.html'
    context_object_name = 'location'

# =====================================
# BRAND MANAGEMENT VIEWS
# =====================================

class BrandListView(BaseInventoryListView):
    model = Brand
    template_name = 'inventory/configuration/brand_list.html'
    context_object_name = 'brands'

class BrandCreateView(BaseInventoryCreateView):
    model = Brand
    fields = ['name', 'description', 'is_active']
    template_name = 'inventory/configuration/brand_form.html'
    success_url = reverse_lazy('inventory:brand_list')

class BrandUpdateView(BaseInventoryUpdateView):
    model = Brand
    fields = ['name', 'description', 'is_active']
    template_name = 'inventory/configuration/brand_form.html'
    success_url = reverse_lazy('inventory:brand_list')

class BrandDeleteView(BaseInventoryDeleteView):
    model = Brand
    template_name = 'inventory/configuration/brand_confirm_delete.html'
    success_url = reverse_lazy('inventory:brand_list')

class BrandDetailView(BaseInventoryDetailView):
    model = Brand
    template_name = 'inventory/configuration/brand_detail.html'
    context_object_name = 'brand'

class BrandProductsView(BaseInventoryListView, ProductRelatedMixin):
    """List products by brand"""
    model = Product
    template_name = 'inventory/brand/brand_products.html'
    context_object_name = 'products'

    def get_queryset(self):
        return self.get_products_queryset().filter(
            brand_id=self.kwargs['pk']
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brand'] = get_object_or_404(Brand, pk=self.kwargs['pk'])
        context['page_title'] = f'Products by {context["brand"].name}'
        return context

# =====================================
# STORAGE LOCATION MANAGEMENT VIEWS
# =====================================

class StorageLocationListView(BaseInventoryListView):
    model = StorageLocation
    template_name = 'inventory/configuration/storage_location_list.html'
    context_object_name = 'storage_locations'

class StorageLocationCreateView(BaseInventoryCreateView):
    model = StorageLocation
    fields = ['name', 'location_type', 'address', 'is_active']
    template_name = 'inventory/configuration/storage_location_form.html'
    success_url = reverse_lazy('inventory:storage_location_list')

class StorageLocationUpdateView(BaseInventoryUpdateView):
    model = StorageLocation
    fields = ['name', 'location_type', 'address', 'is_active']
    template_name = 'inventory/configuration/storage_location_form.html'
    success_url = reverse_lazy('inventory:storage_location_list')

class StorageLocationDeleteView(BaseInventoryDeleteView):
    model = StorageLocation
    template_name = 'inventory/configuration/storage_location_confirm_delete.html'
    success_url = reverse_lazy('inventory:storage_location_list')

class StorageLocationDetailView(BaseInventoryDetailView):
    model = StorageLocation
    template_name = 'inventory/configuration/storage_location_detail.html'
    context_object_name = 'storage_location'

class StorageBinListView(BaseInventoryListView):
    """List storage bins"""
    model = StorageBin
    template_name = 'inventory/configuration/storage_bin_list.html'
    context_object_name = 'bins'
    
    def get_queryset(self):
        location_id = self.kwargs.get('location_id')
        queryset = StorageBin.objects.select_related('location')
        
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        return queryset.order_by('bin_code')

class StorageBinCreateView(BaseInventoryCreateView):
    """Create storage bin"""
    model = StorageBin
    fields = [
        'location', 'bin_code', 'name', 'component_families',
        'row', 'column', 'shelf', 'max_capacity_items',
        'requires_special_handling', 'is_active', 'notes'
    ]
    template_name = 'inventory/configuration/storage_bin_form.html'
    success_url = reverse_lazy('inventory:storage_location_list')

class StorageBinUpdateView(BaseInventoryUpdateView):
    """Update storage bin"""
    model = StorageBin
    fields = [
        'location', 'bin_code', 'name', 'component_families',
        'row', 'column', 'shelf', 'max_capacity_items',
        'requires_special_handling', 'is_active', 'notes'
    ]
    template_name = 'inventory/configuration/storage_bin_form.html'
    success_url = reverse_lazy('inventory:storage_location_list')

class StorageBinDeleteView(BaseInventoryDeleteView):
    """Delete storage bin"""
    model = StorageBin
    template_name = 'inventory/configuration/storage_bin_confirm_delete.html'
    success_url = reverse_lazy('inventory:storage_location_list')

# =====================================
# CATEGORY MANAGEMENT VIEWS
# =====================================

class CategoryListView(BaseInventoryListView):
    model = Category
    template_name = 'inventory/configuration/category_list.html'
    context_object_name = 'categories'

class CategoryCreateView(BaseInventoryCreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/configuration/category_form.html'
    success_url = reverse_lazy('inventory:category_list')

class CategoryUpdateView(BaseInventoryUpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/configuration/category_form.html'
    success_url = reverse_lazy('inventory:category_list')

class CategoryDeleteView(BaseInventoryDeleteView):
    model = Category
    template_name = 'inventory/configuration/category_confirm_delete.html'
    success_url = reverse_lazy('inventory:category_list')

class CategoryDetailView(BaseInventoryDetailView):
    model = Category
    template_name = 'inventory/configuration/category_detail.html'
    context_object_name = 'category'

class CategoryProductsView(BaseInventoryListView, ProductRelatedMixin):
    """List products belonging to a category"""
    model = Product
    template_name = 'inventory/configuration/category_products.html'
    context_object_name = 'products'
    paginate_by = 30

    def get_queryset(self):
        return self.get_products_queryset().filter(
            category_id=self.kwargs['pk']
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = get_object_or_404(Category, pk=self.kwargs['pk'])
        context['page_title'] = f"Products in {context['category'].name}"
        return context

# =====================================
# SUPPLIER MANAGEMENT VIEWS
# =====================================

class SupplierListView(BaseInventoryListView):
    model = Supplier
    template_name = 'inventory/configuration/supplier_list.html'
    context_object_name = 'suppliers'

class SupplierCreateView(BaseInventoryCreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/configuration/supplier_form.html'
    success_url = reverse_lazy('inventory:supplier_list')

class SupplierUpdateView(BaseInventoryUpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/configuration/supplier_form.html'
    success_url = reverse_lazy('inventory:supplier_list')

class SupplierDeleteView(BaseInventoryDeleteView):
    model = Supplier
    template_name = 'inventory/configuration/supplier_confirm_delete.html'
    success_url = reverse_lazy('inventory:supplier_list')

class SupplierDetailView(BaseInventoryDetailView):
    model = Supplier
    template_name = 'inventory/suppliers/supplier_detail.html'
    context_object_name = 'supplier'

class SupplierProductsView(BaseInventoryListView, ProductRelatedMixin):
    """All products sourced from a given supplier"""
    model = Product
    template_name = 'inventory/suppliers/supplier_products.html'
    context_object_name = 'products'

    def get_queryset(self):
        return self.get_products_queryset().filter(
            supplier_id=self.kwargs['pk']
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['supplier'] = get_object_or_404(Supplier, pk=self.kwargs['pk'])
        context['page_title'] = f'Products from {context["supplier"].name}'
        return context

class SupplierPerformanceView(BaseInventoryDetailView):
    """Supplier performance analytics"""
    model = Supplier
    template_name = 'inventory/suppliers/supplier_performance.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = context['supplier']
        
        # Calculate performance metrics
        products = supplier.products.filter(is_active=True)
        performance_data = {
            'total_products': products.count(),
            'total_stock_value': products.aggregate(
                total=Sum(F('current_stock') * F('cost_price'))
            )['total'] or 0,
            'low_stock_products': products.filter(
                current_stock__lte=F('reorder_level')
            ).count(),
        }
        
        context.update({
            'performance_data': performance_data,
            'page_title': f'Performance: {supplier.name}',
        })
        return context

# =====================================
# API ENDPOINTS
# =====================================

def calculate_overhead_for_product(self, import_cost, category_id, supplier_id, weight_grams):
    """Calculate overhead costs for a product"""
    overhead_factors = OverheadFactor.objects.filter(is_active=True)
    total_overhead = Decimal('0.00')
    
    for factor in overhead_factors:
        # Check if factor applies
        applies = True
        
        if factor.applies_to_categories.exists() and category_id:
            applies = applies and factor.applies_to_categories.filter(id=category_id).exists()
        
        if factor.applies_to_suppliers.exists() and supplier_id:
            applies = applies and factor.applies_to_suppliers.filter(id=supplier_id).exists()
        
        if applies:
            cost = factor.calculate_cost(
                product_cost=import_cost,
                order_value=import_cost,
                weight_kg=weight_grams / 1000 if weight_grams else None
            )
            total_overhead += cost
    
    return total_overhead

@login_required
@inventory_permission_required('view')
def product_search_api(request):
    """
    API endpoint for product search with autocomplete support.
    
    Supports integration with quote system and other modules.
    """
    try:
        search_term = request.GET.get('q', '').strip()
        limit = min(int(request.GET.get('limit', 20)), 100)
        
        if len(search_term) < 2:
            return JsonResponse({'success': False, 'error': 'Search term too short'})
        
        products = Product.objects.filter(
            Q(name__icontains=search_term) |
            Q(sku__icontains=search_term) |
            Q(barcode__icontains=search_term),
            is_active=True
        ).select_related('category', 'supplier')[:limit]
        
        results = []
        for product in products:
            results.append({
                'id': product.id,
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'supplier': product.supplier.name,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'current_stock': product.current_stock,
                'available_stock': product.available_stock,
                'stock_status': get_stock_status(product),
                'barcode': product.barcode
            })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Error in product search API: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
@inventory_permission_required('edit')
def stock_adjust_api(request):
    """
    API endpoint for stock adjustments.
    
    Provides programmatic stock adjustment capability for integrations.
    """
    try:
        data = json.loads(request.body)
        
        product_id = data.get('product_id')
        adjustment_type = data.get('adjustment_type')  # 'set', 'add', 'subtract'
        quantity = int(data.get('quantity', 0))
        reason = data.get('reason', 'API adjustment')
        notes = data.get('notes', '')
        
        # Validate inputs
        if not all([product_id, adjustment_type, quantity >= 0]):
            return JsonResponse({
                'success': False,
                'error': 'Missing or invalid parameters'
            })
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Calculate actual adjustment
        if adjustment_type == 'set':
            actual_adjustment = quantity - product.current_stock
        elif adjustment_type == 'add':
            actual_adjustment = quantity
        elif adjustment_type == 'subtract':
            actual_adjustment = -quantity
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid adjustment type'
            })
        
        # Check for negative stock
        if product.current_stock + actual_adjustment < 0:
            return JsonResponse({
                'success': False,
                'error': 'Adjustment would result in negative stock'
            })
        
        # Create stock movement
        movement = create_stock_movement(
            product=product,
            movement_type='adjustment',
            quantity=actual_adjustment,
            reference=f"API adjustment: {reason}",
            user=request.user,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'product_id': product.id,
            'previous_stock': movement.previous_stock,
            'new_stock': movement.new_stock,
            'adjustment': actual_adjustment,
            'movement_id': movement.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error in stock adjust API: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@inventory_permission_required('view')
def check_sku_availability(request):
    """Check if SKU is available for use"""
    sku = request.GET.get('sku', '').strip()
    product_id = request.GET.get('product_id')  # For updates
    
    if not sku:
        return JsonResponse({'available': False, 'error': 'SKU required'})
    
    existing = Product.objects.filter(sku=sku)
    if product_id:
        existing = existing.exclude(id=product_id)
    
    available = not existing.exists()
    
    return JsonResponse({
        'available': available,
        'message': 'SKU available' if available else 'SKU already in use'
    })

@login_required
@inventory_permission_required('view')
def check_barcode_availability(request):
    """Check if barcode is available for use"""
    barcode = request.GET.get('barcode', '').strip()
    product_id = request.GET.get('product_id')  # For updates
    
    if not barcode:
        return JsonResponse({'available': True})  # Empty barcode is allowed
    
    existing = Product.objects.filter(barcode=barcode)
    if product_id:
        existing = existing.exclude(id=product_id)
    
    available = not existing.exists()
    
    return JsonResponse({
        'available': available,
        'message': 'Barcode available' if available else 'Barcode already in use'
    })

@login_required
@inventory_permission_required('view')
def dashboard_metrics_api(request):
    """
    Return dashboard chart data and summary metrics as JSON for AJAX.
    """
    period = int(request.GET.get("period", 30))  # days, default: 30
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period)

    # Prepare time labels
    labels = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(period)]

    # Stock movement trends (simple version)
    movement_data = StockMovement.objects.filter(created_at__range=[start_date, end_date])
    stock_in = []
    stock_out = []
    label_map = {label: i for i, label in enumerate(labels)}
    stock_in_temp = [0 for _ in labels]
    stock_out_temp = [0 for _ in labels]

    for m in movement_data:
        label = m.created_at.strftime('%Y-%m-%d')
        idx = label_map.get(label)
        if idx is not None:
            if m.quantity > 0:
                stock_in_temp[idx] += m.quantity
            else:
                stock_out_temp[idx] += abs(m.quantity)

    # Category distribution (stock value by category)
    category_qs = Category.objects.all()
    category_labels = []
    category_values = []
    for cat in category_qs:
        value = Product.objects.filter(category=cat, is_active=True).aggregate(
            total=Sum(F('current_stock') * F('cost_price'))
        )['total'] or 0
        if value > 0:
            category_labels.append(cat.name)
            category_values.append(float(value))

    data = {
        "success": True,
        "movement_chart": {
            "labels": labels,
            "stock_in": stock_in_temp,
            "stock_out": stock_out_temp,
        },
        "category_chart": {
            "labels": category_labels,
            "values": category_values,
        },
        # Add more dashboard stats if you want!
    }
    return JsonResponse(data)

@login_required
@inventory_permission_required('view')
def recent_activities_api(request):
    """
    Return the most recent inventory activities as JSON.
    """
    activities = []

    # Stock movements (last 10)
    for m in StockMovement.objects.select_related('product', 'created_by').order_by('-created_at')[:10]:
        activities.append({
            "type": "Stock Movement",
            "date": m.created_at.strftime("%Y-%m-%d %H:%M"),
            "user": m.created_by.get_full_name() if m.created_by else "",
            "details": f"{m.get_movement_type_display()} of {m.quantity} - {m.product.name}",
        })
    
    # Product updates (last 5)
    for p in Product.objects.select_related('category').order_by('-updated_at')[:5]:
        activities.append({
            "type": "Product Update",
            "date": p.updated_at.strftime("%Y-%m-%d %H:%M") if p.updated_at else "",
            "user": p.modified_by.get_full_name() if hasattr(p, 'modified_by') and p.modified_by else "",
            "details": f"Product '{p.name}' updated.",
        })

    # Purchase Orders (last 5)
    for po in PurchaseOrder.objects.select_related('supplier').order_by('-created_at')[:5]:
        activities.append({
            "type": "Purchase Order",
            "date": po.created_at.strftime("%Y-%m-%d %H:%M"),
            "user": po.created_by.get_full_name() if po.created_by else "",
            "details": f"PO {po.po_number} for {po.supplier.name}",
        })

    # Sort all by date (desc)
    activities.sort(key=lambda x: x['date'], reverse=True)

    # Limit to latest 20
    data = {
        "success": True,
        "activities": activities[:20],
    }
    return JsonResponse(data)

@login_required
@inventory_permission_required('view')
def critical_alerts_api(request):
    """
    Return all critical (and out-of-stock) reorder alerts as JSON.
    """
    alerts = ReorderAlert.objects.filter(
        priority='critical',  # or whatever value you use for "critical" priority
        status__in=['active', 'acknowledged']
    ).select_related('product')

    data = {
        "success": True,
        "alerts": [
            {
                "id": alert.id,
                "product_id": alert.product.id,
                "product_name": alert.product.name,
                "current_stock": alert.current_stock,
                "reorder_level": alert.reorder_level,
                "suggested_order_quantity": alert.suggested_order_quantity,
                "estimated_cost": float(alert.estimated_cost) if alert.estimated_cost else None,
                "priority": alert.priority,
            }
            for alert in alerts
        ]
    }
    return JsonResponse(data)

@login_required
@inventory_permission_required('view')
def component_family_attributes_api(request, family_id):
    """Get dynamic attributes for a component family"""
    try:
        family = get_object_or_404(ComponentFamily, id=family_id, is_active=True)
        attributes = family.all_attributes
        
        attribute_data = []
        for attr in attributes:
            attribute_data.append({
                'id': attr.id,
                'name': attr.name,
                'field_type': attr.field_type,
                'is_required': attr.is_required,
                'default_value': attr.default_value,
                'help_text': attr.help_text,
                'choice_options': attr.choice_options,
                'min_value': float(attr.min_value) if attr.min_value else None,
                'max_value': float(attr.max_value) if attr.max_value else None,
                'validation_pattern': attr.validation_pattern,
            })
        
        return JsonResponse({
            'success': True,
            'family': family.name,
            'attributes': attribute_data
        })
        
    except ComponentFamily.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Component family not found'})

@login_required
@inventory_permission_required('view')
def calculate_product_cost_api(request, product_id):
    """
    API endpoint: Calculate real-time product cost with current overhead factors.
    Used for quote system and cost analysis.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        quantity = int(request.GET.get('quantity', 1))
        
        # Base cost calculation
        base_cost = product.cost_price * quantity
        
        # Apply overhead factors
        overhead_factors = OverheadFactor.objects.filter(is_active=True)
        overhead_breakdown = []
        total_overhead_amount = Decimal('0')
        
        for factor in overhead_factors:
            overhead_amount = base_cost * (factor.percentage / 100)
            total_overhead_amount += overhead_amount
            overhead_breakdown.append({
                'name': factor.name,
                'percentage': float(factor.percentage),
                'amount': float(overhead_amount),
            })
        
        total_cost = base_cost + total_overhead_amount
        
        # Supplier information
        supplier_info = None
        if product.supplier:
            supplier_info = {
                'name': product.supplier.name,
                'currency': product.supplier.currency,
                'lead_time_days': product.supplier.average_lead_time_days,
                'minimum_order': float(product.supplier.minimum_order_amount),
            }
        
        data = {
            'product_id': product.id,
            'product_name': product.name,
            'sku': product.sku,
            'quantity': quantity,
            'unit_cost': float(product.cost_price),
            'base_cost': float(base_cost),
            'overhead_breakdown': overhead_breakdown,
            'total_overhead': float(total_overhead_amount),
            'total_cost': float(total_cost),
            'unit_total_cost': float(total_cost / quantity) if quantity > 0 else 0,
            'supplier_info': supplier_info,
            'calculated_at': timezone.now().isoformat(),
        }
        
        return JsonResponse({'success': True, 'cost_calculation': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('view')
def product_stock_levels_api(request, product_id):
    """
    API endpoint: Get current stock levels for a product across all locations.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        
        stock_levels = []
        total_available = 0
        total_reserved = 0
        
        for stock_level in product.stock_levels.select_related('location'):
            stock_levels.append({
                'location_id': stock_level.location.id,
                'location_name': stock_level.location.name,
                'location_code': stock_level.location.location_code,
                'quantity': stock_level.quantity,
                'available_quantity': stock_level.available_quantity,
                'reserved_quantity': stock_level.reserved_quantity,
                'last_counted': stock_level.last_counted.isoformat() if stock_level.last_counted else None,
                'last_movement': stock_level.last_movement.isoformat() if stock_level.last_movement else None,
            })
            total_available += stock_level.available_quantity
            total_reserved += stock_level.reserved_quantity
        
        data = {
            'product_id': product.id,
            'product_name': product.name,
            'sku': product.sku,
            'total_stock': product.current_stock,
            'total_available': total_available,
            'total_reserved': total_reserved,
            'reorder_level': product.reorder_level,
            'stock_status': get_stock_status(product),
            'locations': stock_levels,
            'checked_at': timezone.now().isoformat(),
        }
        
        return JsonResponse({'success': True, 'stock_levels': data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('edit')
@require_POST
@csrf_exempt
def reserve_stock_api(request):
    """
    API endpoint: Reserve stock for quotes/orders.
    """
    try:
        data = json.loads(request.body)
        product_id = data['product_id']
        location_id = data.get('location_id')
        quantity = int(data['quantity'])
        reference = data.get('reference', f'RESERVE-{timezone.now().strftime("%Y%m%d%H%M%S")}')
        
        product = get_object_or_404(Product, id=product_id)
        
        if location_id:
            location = get_object_or_404(Location, id=location_id)
            stock_level = get_object_or_404(StockLevel, product=product, location=location)
            
            if stock_level.available_quantity < quantity:
                return JsonResponse({
                    'success': False, 
                    'error': f'Insufficient stock. Available: {stock_level.available_quantity}, Requested: {quantity}'
                }, status=400)
            
            stock_level.reserved_quantity += quantity
            stock_level.save()
            
        else:
            # Reserve from total stock
            available_stock = calculate_available_stock(product)
            if available_stock < quantity:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient stock. Available: {available_stock}, Requested: {quantity}'
                }, status=400)
            
            # Reserve from locations with stock (FIFO)
            remaining_to_reserve = quantity
            for stock_level in product.stock_levels.filter(quantity__gt=0):
                if remaining_to_reserve <= 0:
                    break
                
                available = stock_level.available_quantity
                if available > 0:
                    reserve_qty = min(available, remaining_to_reserve)
                    stock_level.reserved_quantity += reserve_qty
                    stock_level.save()
                    remaining_to_reserve -= reserve_qty
        
        return JsonResponse({
            'success': True,
            'message': f'Reserved {quantity} units of {product.name}',
            'reference': reference,
            'reserved_quantity': quantity,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('edit')
@require_POST
@csrf_exempt
def release_reservation_api(request):
    """
    API endpoint: Release reserved stock.
    """
    try:
        data = json.loads(request.body)
        product_id = data['product_id']
        location_id = data.get('location_id')
        quantity = int(data['quantity'])
        
        product = get_object_or_404(Product, id=product_id)
        
        if location_id:
            location = get_object_or_404(Location, id=location_id)
            stock_level = get_object_or_404(StockLevel, product=product, location=location)
            
            release_qty = min(stock_level.reserved_quantity, quantity)
            stock_level.reserved_quantity -= release_qty
            stock_level.save()
            
        else:
            # Release from all locations
            remaining_to_release = quantity
            for stock_level in product.stock_levels.filter(reserved_quantity__gt=0):
                if remaining_to_release <= 0:
                    break
                
                release_qty = min(stock_level.reserved_quantity, remaining_to_release)
                stock_level.reserved_quantity -= release_qty
                stock_level.save()
                remaining_to_release -= release_qty
        
        return JsonResponse({
            'success': True,
            'message': f'Released {quantity} reserved units of {product.name}',
            'released_quantity': quantity,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('view')
def product_availability_api(request):
    """
    API endpoint: Check product availability for multiple products.
    Used for quote system to validate stock availability.
    """
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            product_requests = data.get('products', [])
        else:
            # GET request with URL parameters
            product_requests = []
            product_ids = request.GET.getlist('product_id')
            quantities = request.GET.getlist('quantity')
            
            for i, product_id in enumerate(product_ids):
                qty = int(quantities[i]) if i < len(quantities) else 1
                product_requests.append({'product_id': product_id, 'quantity': qty})
        
        availability_results = []
        
        for req in product_requests:
            try:
                product = Product.objects.get(id=req['product_id'], is_active=True)
                requested_qty = int(req['quantity'])
                available_qty = calculate_available_stock(product)
                
                is_available = available_qty >= requested_qty
                shortage = max(0, requested_qty - available_qty)
                
                # Estimate restock date if out of stock
                restock_estimate = None
                if shortage > 0 and product.supplier:
                    lead_time = product.supplier.average_lead_time_days or 7
                    restock_estimate = (timezone.now() + timedelta(days=lead_time)).date().isoformat()
                
                availability_results.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'sku': product.sku,
                    'requested_quantity': requested_qty,
                    'available_quantity': available_qty,
                    'is_available': is_available,
                    'shortage': shortage,
                    'restock_estimate': restock_estimate,
                    'current_stock': product.current_stock,
                    'reorder_level': product.reorder_level,
                })
                
            except Product.DoesNotExist:
                availability_results.append({
                    'product_id': req['product_id'],
                    'error': 'Product not found or inactive',
                    'is_available': False,
                })
        
        return JsonResponse({
            'success': True,
            'availability': availability_results,
            'checked_at': timezone.now().isoformat(),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('edit')
@require_POST
def generate_reorder_list_api(request):
    """Generate and return reorder list for download"""
    try:
        # Get filter parameters
        data = json.loads(request.body) if request.body else {}
        supplier_id = data.get('supplier_id')
        category_id = data.get('category_id')
        priority = data.get('priority')  # 'critical', 'high', 'medium'
        
        # Base query
        products = Product.objects.filter(
            is_active=True,
            total_stock__lte=F('reorder_level')
        ).select_related('supplier', 'category', 'brand', 'supplier_currency')
        
        # Apply filters
        if supplier_id:
            products = products.filter(supplier_id=supplier_id)
        if category_id:
            products = products.filter(category_id=category_id)
        
        # Generate reorder list
        reorder_data = []
        total_order_value = Decimal('0.00')
        
        for product in products:
            # Determine priority
            if product.total_stock == 0:
                item_priority = 'critical'
            elif product.total_stock <= (product.reorder_level * 0.5):
                item_priority = 'high'
            else:
                item_priority = 'medium'
            
            # Filter by priority if specified
            if priority and item_priority != priority:
                continue
            
            # Calculate order details
            recommended_qty = max(
                product.reorder_quantity,
                product.supplier_minimum_order_quantity,
                product.reorder_level - product.total_stock + 10
            )
            
            unit_cost = product.get_preferred_supplier_price(recommended_qty)
            order_value = unit_cost * recommended_qty
            total_order_value += order_value
            
            reorder_data.append({
                'supplier': product.supplier.name,
                'supplier_email': product.supplier.email,
                'sku': product.sku,
                'supplier_sku': product.supplier_sku,
                'name': product.name,
                'current_stock': product.total_stock,
                'reorder_level': product.reorder_level,
                'recommended_quantity': recommended_qty,
                'unit_cost': float(unit_cost),
                'currency': product.supplier_currency.code,
                'order_value': float(order_value),
                'lead_time_days': product.supplier_lead_time_days,
                'moq': product.supplier_minimum_order_quantity,
                'priority': item_priority
            })
        
        return JsonResponse({
            'success': True,
            'reorder_list': reorder_data,
            'summary': {
                'total_items': len(reorder_data),
                'total_order_value': float(total_order_value),
                'suppliers': len(set(item['supplier'] for item in reorder_data))
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating reorder list: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_http_methods(["GET"])
def product_attributes_api(request, product_id):
    """API for product attributes"""
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        data = {
            'product_id': product.id,
            'attributes': product.get_dynamic_attributes(),  # Assuming this method exists
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def stock_adjustment_api(request):
    """API for stock adjustments"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        adjustment = data.get('adjustment')
        notes = data.get('notes', '')
        
        product = Product.objects.get(id=product_id, is_active=True)
        product.current_stock += adjustment
        product.save()
        
        # Create movement record
        create_stock_movement(
            product=product,
            movement_type='adjustment',
            quantity=adjustment,
            user=request.user,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'new_stock': product.current_stock
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@require_http_methods(["POST"])
def stock_transfer_api(request):
    """API for stock transfers"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        from_location_id = data.get('from_location_id')
        to_location_id = data.get('to_location_id')
        quantity = data.get('quantity')
        
        product = Product.objects.get(id=product_id, is_active=True)
        from_location = Location.objects.get(id=from_location_id)
        to_location = Location.objects.get(id=to_location_id)
        
        # Process transfer
        from_stock = StockLevel.objects.get(product=product, location=from_location)
        to_stock, created = StockLevel.objects.get_or_create(
            product=product, 
            location=to_location,
            defaults={'quantity': 0}
        )
        
        from_stock.quantity -= quantity
        to_stock.quantity += quantity
        
        from_stock.save()
        to_stock.save()
        
        # Create movement records
        create_stock_movement(
            product=product,
            movement_type='transfer_out',
            quantity=-quantity,
            user=request.user,
            from_location=from_location,
            to_location=to_location
        )
        
        create_stock_movement(
            product=product,
            movement_type='transfer_in',
            quantity=quantity,
            user=request.user,
            from_location=from_location,
            to_location=to_location
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@require_http_methods(["GET"])
def reorder_suggestions_api(request):
    """API for reorder suggestions"""
    low_stock_products = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level')
    ).select_related('supplier')
    
    suggestions = []
    for product in low_stock_products:
        suggestions.append({
            'product_id': product.id,
            'product_name': product.name,
            'current_stock': product.current_stock,
            'reorder_level': product.reorder_level,
            'reorder_quantity': product.reorder_quantity,
            'supplier': product.supplier.name if product.supplier else '',
            'cost_price': str(product.cost_price),
            'total_cost': str(product.reorder_quantity * product.cost_price),
        })
    
    return JsonResponse({'suggestions': suggestions})

# =====================================
# INTEGRATION ENDPOINTS FOR QUOTE SYSTEM
# =====================================

@login_required
@inventory_permission_required('view')
def quote_products_api(request):
    """
    API endpoint for quote system to search and retrieve products.
    
    Provides product information optimized for quote creation.
    """
    try:
        from .utils import get_products_for_quote_system
        
        search_term = request.GET.get('search')
        category_id = request.GET.get('category')
        supplier_id = request.GET.get('supplier')
        limit = min(int(request.GET.get('limit', 50)), 100)
        
        # Get category and supplier objects if provided
        category = None
        supplier = None
        
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass
        
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Supplier.DoesNotExist:
                pass
        
        products = get_products_for_quote_system(
            search_term=search_term,
            category=category,
            supplier=supplier,
            limit=limit
        )
        
        return JsonResponse({
            'success': True,
            'products': products,
            'count': len(products)
        })
        
    except Exception as e:
        logger.error(f"Error in quote products API: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
@inventory_permission_required('view')
def check_quote_availability_api(request):
    """
    Check stock availability for quote items.
    
    Used by quote system to validate stock before quote creation.
    """
    try:
        data = json.loads(request.body)
        quote_items = data.get('items', [])
        
        if not quote_items:
            return JsonResponse({'success': False, 'error': 'No items provided'})
        
        from .utils import check_stock_availability_for_quote
        
        availability = check_stock_availability_for_quote(quote_items)
        
        # Check if all items can be fulfilled
        all_available = all(
            item.get('can_fulfill', False) 
            for item in availability.values() 
            if 'error' not in item
        )
        
        return JsonResponse({
            'success': True,
            'all_available': all_available,
            'availability': availability
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error checking quote availability: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
@inventory_permission_required('edit')
def reserve_for_quote_api(request):
    """
    Reserve stock for quote items.
    
    Creates stock reservations that can be released if quote is not accepted.
    """
    try:
        data = json.loads(request.body)
        quote_items = data.get('items', [])
        quote_reference = data.get('quote_reference', '')
        
        if not quote_items or not quote_reference:
            return JsonResponse({
                'success': False,
                'error': 'Items and quote reference required'
            })
        
        from .utils import reserve_stock_for_quote
        
        results = reserve_stock_for_quote(
            quote_items=quote_items,
            quote_reference=quote_reference,
            user=request.user
        )
        
        return JsonResponse(results)
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error reserving stock for quote: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

# =====================================
# BUSINESS INTELLIGENCE VIEWS
# =====================================

@login_required
@inventory_permission_required('view')
def inventory_analytics_view(request):
    """Inventory analytics dashboard"""
    
    # Get ABC classification
    products = Product.objects.filter(is_active=True)
    abc_classification = InventoryAnalytics.get_abc_classification(products)
    
    # Calculate inventory turnover for top products
    top_products = products.annotate(
        stock_value=F('current_stock') * F('cost_price')
    ).order_by('-stock_value')[:20]
    
    # Stock aging analysis
    stock_aging_data = []
    for product in top_products:
        days_in_stock = calculate_days_of_stock(product)
        stock_aging_data.append({
            'product': product,
            'days_in_stock': days_in_stock,
            'stock_value': product.current_stock * product.cost_price
        })
    
    context = {
        'page_title': 'Inventory Analytics',
        'abc_classification': abc_classification,
        'stock_aging_data': stock_aging_data,
        'total_products': products.count(),
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'inventory/analytics/inventory_analytics.html', context)

# =====================================
# REPORTS VIEWS
# =====================================

class AlertsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/alerts/reorder_alert_list.html"

    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_alerts = ReorderAlert.objects.filter(
            status__in=['active', 'acknowledged']
        ).select_related('product', 'suggested_supplier').order_by('priority', '-created_at')
        context['active_alerts'] = active_alerts
        return context

class CustomReportView(LoginRequiredMixin, TemplateView):
    """Custom report builder"""
    template_name = 'inventory/reports/custom_report.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@login_required
@inventory_permission_required('view')
def inventory_reports_view(request):
    """Inventory reports dashboard"""
    return render(request, 'inventory/reports.html', {
        'report_types': [
            {'name': 'Stock Valuation Report', 'url': 'stock_valuation'},
            {'name': 'Low Stock Report', 'url': 'low_stock'},
            {'name': 'Supplier Performance', 'url': 'supplier_performance'},
            {'name': 'Category Analysis', 'url': 'category_analysis'},
            {'name': 'Markup Analysis', 'url': 'markup_analysis'},
            {'name': 'ABC Analysis', 'url': 'abc_analysis'},
        ]
    })

@login_required
@inventory_permission_required('view')
def stock_valuation_report(request):
    """Generate stock valuation report"""
    # Implementation for stock valuation report
    products = Product.objects.filter(is_active=True).select_related(
        'category', 'supplier', 'brand'
    ).order_by('category__name', 'name')
    
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stock_valuation_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Category', 'SKU', 'Product Name', 'Brand', 'Supplier',
            'Stock Quantity', 'Unit Cost (USD)', 'Total Value (USD)',
            'Unit Selling Price', 'Potential Revenue', 'Potential Profit'
        ])
        
        for product in products:
            writer.writerow([
                product.category.name,
                product.sku,
                product.name,
                product.brand.name,
                product.supplier.name,
                product.total_stock,
                product.total_cost_price_usd,
                product.stock_value_usd,
                product.selling_price,
                product.total_stock * product.selling_price,
                product.total_stock * product.profit_per_unit_usd
            ])
        
        return response
    
    # Return HTML version
    context = {'products': products}
    return render(request, 'inventory/reports/stock_valuation.html', context)

def supplier_details_api(request, pk):
    """
    API endpoint for AJAX: Returns supplier details as JSON.
    """
    try:
        supplier = Supplier.objects.get(pk=pk)
        data = {
            'id': supplier.id,
            'name': supplier.name,
            'supplier_code': supplier.supplier_code,
            'supplier_type': supplier.get_supplier_type_display(),
            'email': supplier.email,
            'phone': supplier.phone,
            'address': f"{supplier.address_line_1} {supplier.address_line_2} {supplier.city} {supplier.country}".strip(),
            'currency': supplier.currency,
            'minimum_order_amount': float(supplier.minimum_order_amount),
            'average_lead_time_days': supplier.average_lead_time_days,
            'reliability_rating': float(supplier.reliability_rating),
            'is_active': supplier.is_active,
            'is_preferred': supplier.is_preferred,
            # Add more fields if needed!
        }
        return JsonResponse({'success': True, 'supplier': data})
    except Supplier.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Supplier not found'}, status=404)

@login_required
@inventory_permission_required('view')
def quick_search_view(request):
    """Quick search across all inventory items"""
    search_term = request.GET.get('q', '').strip()
    
    if len(search_term) < 2:
        return JsonResponse({'results': []})
    
    # Search products
    products = Product.objects.filter(
        Q(name__icontains=search_term) |
        Q(sku__icontains=search_term),
        is_active=True
    )[:10]
    
    results = [
        {
            'type': 'product',
            'id': p.id,
            'title': p.name,
            'subtitle': p.sku,
            'url': reverse('inventory:product_detail', args=[p.id])
        }
        for p in products
    ]
    
    return JsonResponse({'results': results})

@login_required
@inventory_permission_required('view')
def stock_movements_export(request):
    """
    Export stock movements to CSV.
    """
    # Optional: Add filter params, e.g. by date, type, etc.
    movements = StockMovement.objects.select_related('product', 'from_location', 'to_location', 'created_by').order_by('-created_at')

    # Prepare CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_movements.csv"'

    writer = csv.writer(response)
    # Header
    writer.writerow([
        'Date', 'Product SKU', 'Product Name', 'Type', 'Quantity',
        'From Location', 'To Location', 'Reference', 'Previous Stock',
        'New Stock', 'Created By', 'Notes'
    ])

    # Rows
    for m in movements:
        writer.writerow([
            m.created_at.strftime('%Y-%m-%d %H:%M'),
            m.product.sku,
            m.product.name,
            m.get_movement_type_display(),
            m.quantity,
            m.from_location.name if m.from_location else '',
            m.to_location.name if m.to_location else '',
            m.reference,
            m.previous_stock,
            m.new_stock,
            m.created_by.get_full_name() if m.created_by else '',
            m.notes or '',
        ])
    return response

@login_required
@inventory_permission_required('view')
def reports_dashboard(request):
    """
    Enterprise-grade inventory reports dashboard view.
    Aggregates inventory and operational KPIs, and supports extensible reporting.
    """
    # Key operational stats
    total_products = Product.objects.filter(is_active=True).count()
    total_stock_value = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_stock') * F('cost_price'))
    )['total'] or 0

    low_stock_count = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level'),
        current_stock__gt=0
    ).count()

    out_of_stock_count = Product.objects.filter(
        is_active=True,
        current_stock=0
    ).count()

    # Per-category and per-supplier breakdowns
    top_categories = Category.objects.annotate(
        product_count=Count('products', filter=Q(products__is_active=True)),
        stock_value=Sum(F('products__current_stock') * F('products__cost_price'))
    ).order_by('-stock_value')[:6]

    top_suppliers = Supplier.objects.annotate(
        product_count=Count('products', filter=Q(products__is_active=True)),
        stock_value=Sum(F('products__current_stock') * F('products__cost_price'))
    ).order_by('-stock_value')[:6]

    # Recent stock movements
    recent_movements = StockMovement.objects.select_related('product', 'created_by').order_by('-created_at')[:10]

    # Alerts and overdue POs
    active_alerts = ReorderAlert.objects.filter(
        status__in=['active', 'acknowledged']
    ).select_related('product', 'suggested_supplier').order_by('-priority', '-created_at')[:10]

    overdue_pos = PurchaseOrder.objects.filter(
        status__in=['sent', 'acknowledged'],
        expected_delivery_date__lt=timezone.now().date()
    ).select_related('supplier').order_by('expected_delivery_date')[:5]

    # Stock take analytics
    pending_stock_takes = StockTake.objects.filter(
        status__in=['planned', 'in_progress']
    ).order_by('scheduled_date')[:3]

    # Historical analytics - can be expanded with real BI/analytics backend
    movements_last_30_days = StockMovement.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()
    total_value_last_30_days = StockMovement.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).aggregate(
        value=Sum(F('quantity') * F('product__cost_price'))
    )['value'] or 0

    context = {
        # KPIs for dashboard cards
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        # Analytics
        'movements_last_30_days': movements_last_30_days,
        'total_value_last_30_days': total_value_last_30_days,
        'top_categories': top_categories,
        'top_suppliers': top_suppliers,
        'recent_movements': recent_movements,
        'active_alerts': active_alerts,
        'overdue_pos': overdue_pos,
        'pending_stock_takes': pending_stock_takes,
    }
    
    return render(request, "inventory/reports/reports_dashboard.html", context)

@login_required
@inventory_permission_required('view')
def export_report(request, report_type):
    """
    Export inventory reports (valuation, etc) as Excel (CSV) or PDF (placeholder).
    """
    # Only 'valuation' is supported here; you can extend for more report types!
    if report_type != "valuation":
        return HttpResponse("Unsupported report type", status=400)

    export_format = request.GET.get('export', 'excel')

    # Filter products as in your valuation view
    products = Product.objects.filter(is_active=True).select_related('category', 'supplier')

    # Handle export format
    if export_format == "excel":
        # Export as CSV (Excel-compatible)
        response = HttpResponse(content_type='text/csv')
        filename = f"inventory_valuation_{timezone.now().date()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            "SKU", "Product Name", "Category", "Supplier",
            "Quantity", "Cost Price", "Selling Price", "Total Value", "Margin (%)"
        ])
        for p in products:
            margin_pct = ((p.selling_price - p.cost_price) / p.cost_price * 100) if p.cost_price else 0
            writer.writerow([
                p.sku, p.name,
                p.category.name if p.category else "",
                p.supplier.name if p.supplier else "",
                p.current_stock,
                "%.2f" % p.cost_price,
                "%.2f" % p.selling_price,
                "%.2f" % (p.current_stock * p.cost_price),
                "%.1f" % margin_pct
            ])
        return response

    elif export_format == "pdf":
        # For real systems, use ReportLab, xhtml2pdf, or WeasyPrint here!
        # Here, return a simple HTML-to-PDF placeholder.
        context = {
            "products": products,
            "generated_on": timezone.now(),
        }
        # Render a minimal HTML template; real implementation would use a PDF generator
        return render(request, "inventory/reports/valuation_pdf.html", context)

    else:
        return HttpResponse("Unknown export format", status=400)

@login_required
@inventory_permission_required('view')
def stock_aging_report(request):
    """
    Stock aging report to identify slow-moving and dead stock.
    Critical for inventory optimization and cash flow management.
    """
    try:
        # Date ranges for aging analysis
        today = timezone.now().date()
        date_ranges = [
            ('0-30', today - timedelta(days=30), today),
            ('31-60', today - timedelta(days=60), today - timedelta(days=31)),
            ('61-90', today - timedelta(days=90), today - timedelta(days=61)),
            ('91-180', today - timedelta(days=180), today - timedelta(days=91)),
            ('180+', None, today - timedelta(days=180)),
        ]
        
        # Get all active products with their last movement dates
        products = Product.objects.filter(
            is_active=True,
            current_stock__gt=0
        ).select_related('category', 'supplier').annotate(
            last_movement_date=Max('stock_movements__created_at')
        )
        
        aging_data = []
        total_value = Decimal('0')
        
        for product in products:
            last_movement = product.last_movement_date
            
            if last_movement:
                days_since_movement = (today - last_movement.date()).days
            else:
                # If no movements, use creation date
                days_since_movement = (today - product.created_at.date()).days
            
            # Determine aging category
            aging_category = '180+'
            for category, start_date, end_date in date_ranges:
                if start_date is None:  # 180+ category
                    if days_since_movement >= 180:
                        aging_category = category
                        break
                else:
                    if start_date <= (today - timedelta(days=days_since_movement)) <= end_date:
                        aging_category = category
                        break
            
            stock_value = product.current_stock * product.cost_price
            total_value += stock_value
            
            aging_data.append({
                'product': product,
                'days_since_movement': days_since_movement,
                'last_movement_date': last_movement,
                'aging_category': aging_category,
                'stock_value': stock_value,
                'current_stock': product.current_stock,
            })
        
        # Group by aging category
        aging_summary = {}
        for category, _, _ in date_ranges:
            category_items = [item for item in aging_data if item['aging_category'] == category]
            category_value = sum(item['stock_value'] for item in category_items)
            
            aging_summary[category] = {
                'count': len(category_items),
                'value': category_value,
                'percentage': (category_value / total_value * 100) if total_value > 0 else 0,
                'items': sorted(category_items, key=lambda x: x['days_since_movement'], reverse=True)[:10]  # Top 10
            }
        
        return render(request, 'inventory/reports/stock_aging_report.html', {
            'page_title': 'Stock Aging Report',
            'aging_summary': aging_summary,
            'total_value': total_value,
            'total_products': len(aging_data),
            'date_ranges': date_ranges,
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate stock aging report: {str(e)}')
        return redirect('inventory:inventory_reports')

@login_required
@inventory_permission_required('view')
def inventory_turnover_report(request):
    """
    Inventory turnover analysis for performance metrics.
    Shows how efficiently inventory is being managed.
    """
    try:
        # Get date range (default last 12 months)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
        
        if request.GET.get('start_date'):
            start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
        if request.GET.get('end_date'):
            end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
        
        # Calculate turnover for each product
        products = Product.objects.filter(is_active=True).select_related('category', 'supplier')
        turnover_data = []
        
        for product in products:
            # Calculate average inventory (simplified: current stock)
            avg_inventory = product.current_stock
            
            # Calculate cost of goods sold (from sales movements)
            cogs = product.stock_movements.filter(
                movement_type='sale',
                created_at__date__range=[start_date, end_date]
            ).aggregate(
                total_sold=Sum('quantity')
            )['total_sold'] or 0
            
            cogs_value = cogs * product.cost_price
            
            # Calculate turnover ratio
            if avg_inventory > 0:
                turnover_ratio = cogs / avg_inventory
                days_on_hand = 365 / turnover_ratio if turnover_ratio > 0 else 365
            else:
                turnover_ratio = 0
                days_on_hand = 0 if cogs > 0 else 365
            
            # Classify performance
            if turnover_ratio >= 12:  # Monthly turnover
                performance = 'Excellent'
            elif turnover_ratio >= 6:  # Bi-monthly
                performance = 'Good'
            elif turnover_ratio >= 4:  # Quarterly
                performance = 'Average'
            elif turnover_ratio >= 2:  # Semi-annual
                performance = 'Below Average'
            else:
                performance = 'Poor'
            
            turnover_data.append({
                'product': product,
                'avg_inventory': avg_inventory,
                'cogs': cogs,
                'cogs_value': cogs_value,
                'turnover_ratio': round(turnover_ratio, 2),
                'days_on_hand': round(days_on_hand, 1),
                'performance': performance,
                'stock_value': avg_inventory * product.cost_price,
            })
        
        # Sort by turnover ratio (descending)
        turnover_data.sort(key=lambda x: x['turnover_ratio'], reverse=True)
        
        # Calculate summary statistics
        total_stock_value = sum(item['stock_value'] for item in turnover_data)
        avg_turnover = sum(item['turnover_ratio'] for item in turnover_data) / len(turnover_data) if turnover_data else 0
        
        # Performance distribution
        performance_summary = {}
        for item in turnover_data:
            perf = item['performance']
            if perf not in performance_summary:
                performance_summary[perf] = {'count': 0, 'value': 0}
            performance_summary[perf]['count'] += 1
            performance_summary[perf]['value'] += item['stock_value']
        
        return render(request, 'inventory/reports/inventory_turnover_report.html', {
            'page_title': 'Inventory Turnover Report',
            'turnover_data': turnover_data,
            'total_stock_value': total_stock_value,
            'avg_turnover': round(avg_turnover, 2),
            'performance_summary': performance_summary,
            'start_date': start_date,
            'end_date': end_date,
            'date_range_days': (end_date - start_date).days,
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate turnover report: {str(e)}')
        return redirect('inventory:inventory_reports')

@login_required
@inventory_permission_required('view')
def abc_analysis_report(request):
    """
    ABC analysis to classify products by value contribution.
    A = High value (70-80% of total), B = Medium (15-20%), C = Low (5-10%)
    """
    try:
        # Get all products with their stock values
        products = Product.objects.filter(is_active=True).select_related('category', 'supplier')
        
        product_data = []
        total_value = Decimal('0')
        
        for product in products:
            stock_value = product.current_stock * product.cost_price
            total_value += stock_value
            
            # Calculate annual sales (last 12 months)
            annual_sales = product.stock_movements.filter(
                movement_type='sale',
                created_at__gte=timezone.now() - timedelta(days=365)
            ).aggregate(
                total_sold=Sum('quantity')
            )['total_sold'] or 0
            
            annual_sales_value = annual_sales * product.selling_price
            
            product_data.append({
                'product': product,
                'stock_value': stock_value,
                'annual_sales': annual_sales,
                'annual_sales_value': annual_sales_value,
            })
        
        # Sort by stock value (descending)
        product_data.sort(key=lambda x: x['stock_value'], reverse=True)
        
        # Calculate cumulative percentages and assign ABC categories
        cumulative_value = Decimal('0')
        for i, item in enumerate(product_data):
            cumulative_value += item['stock_value']
            cumulative_percentage = (cumulative_value / total_value * 100) if total_value > 0 else 0
            
            # Assign ABC category
            if cumulative_percentage <= 80:
                category = 'A'
            elif cumulative_percentage <= 95:
                category = 'B'
            else:
                category = 'C'
            
            item['cumulative_value'] = cumulative_value
            item['cumulative_percentage'] = round(cumulative_percentage, 2)
            item['abc_category'] = category
            item['rank'] = i + 1
        
        # Calculate category summaries
        abc_summary = {}
        for category in ['A', 'B', 'C']:
            category_items = [item for item in product_data if item['abc_category'] == category]
            category_value = sum(item['stock_value'] for item in category_items)
            
            abc_summary[category] = {
                'count': len(category_items),
                'value': category_value,
                'percentage': (category_value / total_value * 100) if total_value > 0 else 0,
                'items': category_items[:20]  # Top 20 for display
            }
        
        return render(request, 'inventory/reports/abc_analysis_report.html', {
            'page_title': 'ABC Analysis Report',
            'abc_summary': abc_summary,
            'total_value': total_value,
            'total_products': len(product_data),
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate ABC analysis: {str(e)}')
        return redirect('inventory:inventory_reports')

@login_required
@inventory_permission_required('view')
def supplier_performance_report(request):
    """
    Comprehensive supplier performance analysis.
    Evaluates delivery times, quality, reliability, and cost-effectiveness.
    """
    try:
        # Get all active suppliers
        suppliers = Supplier.objects.filter(is_active=True)
        supplier_data = []
        
        for supplier in suppliers:
            # Get purchase orders from last 12 months
            recent_pos = supplier.purchase_orders.filter(
                order_date__gte=timezone.now().date() - timedelta(days=365)
            )
            
            # Calculate metrics
            total_orders = recent_pos.count()
            total_value = recent_pos.aggregate(Sum('total_amount'))['total_amount'] or Decimal('0')
            
            # Delivery performance
            completed_orders = recent_pos.filter(status='received')
            on_time_orders = completed_orders.filter(
                actual_delivery_date__lte=F('expected_delivery_date')
            ).count()
            
            delivery_performance = (on_time_orders / completed_orders.count() * 100) if completed_orders.count() > 0 else 0
            
            # Average lead time
            actual_lead_times = []
            for po in completed_orders:
                if po.actual_delivery_date and po.order_date:
                    lead_time = (po.actual_delivery_date - po.order_date).days
                    actual_lead_times.append(lead_time)
            
            avg_lead_time = sum(actual_lead_times) / len(actual_lead_times) if actual_lead_times else 0
            
            # Quality metrics (from received items)
            quality_issues = 0
            total_items_received = 0
            for po in completed_orders:
                for item in po.items.all():
                    total_items_received += item.quantity_received
                    if item.quality_check_passed is False:
                        quality_issues += item.quantity_received
            
            quality_rate = ((total_items_received - quality_issues) / total_items_received * 100) if total_items_received > 0 else 100
            
            # Cost competitiveness (simplified)
            avg_cost_per_item = total_value / total_items_received if total_items_received > 0 else Decimal('0')
            
            # Overall score (weighted average)
            delivery_weight = 0.4
            quality_weight = 0.4
            reliability_weight = 0.2
            
            overall_score = (
                delivery_performance * delivery_weight +
                quality_rate * quality_weight +
                supplier.reliability_rating * 10 * reliability_weight  # Convert 1-10 to percentage
            )
            
            supplier_data.append({
                'supplier': supplier,
                'total_orders': total_orders,
                'total_value': total_value,
                'delivery_performance': round(delivery_performance, 1),
                'avg_lead_time': round(avg_lead_time, 1),
                'expected_lead_time': supplier.average_lead_time_days,
                'quality_rate': round(quality_rate, 1),
                'quality_issues': quality_issues,
                'total_items_received': total_items_received,
                'avg_cost_per_item': avg_cost_per_item,
                'overall_score': round(overall_score, 1),
                'reliability_rating': supplier.reliability_rating,
            })
        
        # Sort by overall score (descending)
        supplier_data.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return render(request, 'inventory/reports/supplier_performance_report.html', {
            'page_title': 'Supplier Performance Report',
            'supplier_data': supplier_data,
            'total_suppliers': len(supplier_data),
            'report_period': '12 months',
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate supplier performance report: {str(e)}')
        return redirect('inventory:inventory_reports')

@login_required
@inventory_permission_required('view')
def category_analysis_report(request):
    """
    Category performance analysis for business insights.
    Shows which product categories are performing best.
    """
    try:
        categories = Category.objects.filter(is_active=True)
        category_data = []
        
        for category in categories:
            products = category.products.filter(is_active=True)
            
            # Stock metrics
            total_products = products.count()
            total_stock_value = sum(p.current_stock * p.cost_price for p in products)
            total_stock_units = sum(p.current_stock for p in products)
            
            # Sales metrics (last 6 months)
            six_months_ago = timezone.now() - timedelta(days=180)
            category_sales = StockMovement.objects.filter(
                product__category=category,
                movement_type='sale',
                created_at__gte=six_months_ago
            ).aggregate(
                total_units_sold=Sum('quantity'),
            )['total_units_sold'] or 0
            
            # Calculate average selling price for the category
            avg_selling_price = products.aggregate(Avg('selling_price'))['selling_price__avg'] or Decimal('0')
            sales_value = category_sales * avg_selling_price
            
            # Low stock products
            low_stock_count = products.filter(current_stock__lte=F('reorder_level')).count()
            
            # Profit margins
            avg_cost_price = products.aggregate(Avg('cost_price'))['cost_price__avg'] or Decimal('0')
            avg_margin = avg_selling_price - avg_cost_price
            avg_margin_percent = (avg_margin / avg_selling_price * 100) if avg_selling_price > 0 else 0
            
            # Turnover rate (simplified)
            turnover_rate = (category_sales / total_stock_units) if total_stock_units > 0 else 0
            
            category_data.append({
                'category': category,
                'total_products': total_products,
                'total_stock_value': total_stock_value,
                'total_stock_units': total_stock_units,
                'sales_units': category_sales,
                'sales_value': sales_value,
                'low_stock_count': low_stock_count,
                'avg_selling_price': avg_selling_price,
                'avg_cost_price': avg_cost_price,
                'avg_margin': avg_margin,
                'avg_margin_percent': round(avg_margin_percent, 2),
                'turnover_rate': round(turnover_rate, 2),
            })
        
        # Sort by sales value (descending)
        category_data.sort(key=lambda x: x['sales_value'], reverse=True)
        
        # Calculate totals
        total_sales_value = sum(item['sales_value'] for item in category_data)
        total_stock_value = sum(item['total_stock_value'] for item in category_data)
        
        return render(request, 'inventory/reports/category_analysis_report.html', {
            'page_title': 'Category Analysis Report',
            'category_data': category_data,
            'total_categories': len(category_data),
            'total_sales_value': total_sales_value,
            'total_stock_value': total_stock_value,
            'report_period': '6 months',
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate category analysis: {str(e)}')
        return redirect('inventory:inventory_reports')

@login_required
@inventory_permission_required('view')
def supplier_comparison_report(request):
    """Compare suppliers"""
    context = {
        'page_title': 'Supplier Comparison Report',
    }
    return render(request, 'inventory/reports/supplier_comparison.html', context)

@login_required
@inventory_permission_required('view')
def purchase_analysis_report(request):
    """Purchase analysis report"""
    context = {
        'page_title': 'Purchase Analysis Report',
    }
    return render(request, 'inventory/reports/purchase_analysis.html', context)

@login_required
@inventory_permission_required('view')
def cost_analysis_report(request):
    """Cost analysis report"""
    context = {
        'page_title': 'Cost Analysis Report',
    }
    return render(request, 'inventory/reports/cost_analysis.html', context)

@login_required
@inventory_permission_required('view')
def margin_analysis_report(request):
    """Margin analysis report"""
    context = {
        'page_title': 'Margin Analysis Report',
    }
    return render(request, 'inventory/reports/margin_analysis.html', context)

@login_required
@inventory_permission_required('view')
def profitability_report(request):
    """Profitability report"""
    context = {
        'page_title': 'Profitability Report',
    }
    return render(request, 'inventory/reports/profitability.html', context)

@login_required
@inventory_permission_required('view')
def tax_compliance_report(request):
    """Tax compliance report"""
    context = {
        'page_title': 'Tax Compliance Report',
    }
    return render(request, 'inventory/reports/tax_compliance.html', context)

@login_required
@inventory_permission_required('view')
def brand_performance_report(request):
    """Brand performance report"""
    brands = Brand.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    )
    
    context = {
        'page_title': 'Brand Performance Report',
        'brands': brands,
        'report_date': timezone.now().date(),
    }
    return render(request, 'inventory/reports/brand_performance.html', context)

@login_required
@inventory_permission_required('view')
def executive_summary_report(request):
    """Executive summary report"""
    # Calculate key metrics
    total_products = Product.objects.filter(is_active=True).count()
    total_stock_value = Product.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_stock') * F('cost_price'))
    )['total'] or 0
    
    low_stock_count = Product.objects.filter(
        is_active=True,
        current_stock__lte=F('reorder_level')
    ).count()
    
    pending_po_count = PurchaseOrder.objects.filter(
        status__in=['draft', 'sent', 'acknowledged']
    ).count()
    
    context = {
        'page_title': 'Executive Summary Report',
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'low_stock_count': low_stock_count,
        'pending_po_count': pending_po_count,
        'report_date': timezone.now().date(),
    }
    return render(request, 'inventory/reports/executive_summary.html', context)

# =====================================
# STOCK TAKE MANAGEMENT VIEWS
# =====================================

class StockTakeListView(LoginRequiredMixin, ListView):
    """
    Manage stock take operations for inventory accuracy.
    """
    model = StockTake
    template_name = 'inventory/stock_take/stock_take_list.html'
    context_object_name = 'stock_takes'
    paginate_by = 20
    
    @method_decorator(stock_take_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        return StockTake.objects.select_related(
            'location', 'created_by'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate summary metrics
        stock_takes = self.get_queryset()
        summary = {
            'total_stock_takes': stock_takes.count(),
            'pending': stock_takes.filter(status='pending').count(),
            'in_progress': stock_takes.filter(status='in_progress').count(),
            'completed': stock_takes.filter(status='completed').count(),
        }
        
        context.update({
            'page_title': 'Stock Take Management',
            'summary': summary,
        })
        return context

class StockTakeCreateView(LoginRequiredMixin, CreateView):
    """
    Create new stock take operations.
    """
    model = StockTake
    form_class = StockTakeForm
    template_name = 'inventory/stock_take/stock_take_form.html'
    
    @method_decorator(stock_take_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # Create stock take items for all products at the location
        if form.instance.location:
            stock_levels = StockLevel.objects.filter(location=form.instance.location)
            for stock_level in stock_levels:
                StockTakeItem.objects.create(
                    stock_take=form.instance,
                    product=stock_level.product,
                    expected_quantity=stock_level.quantity,
                )
        else:
            # All locations - create for all products
            products = Product.objects.filter(is_active=True)
            for product in products:
                StockTakeItem.objects.create(
                    stock_take=form.instance,
                    product=product,
                    expected_quantity=product.current_stock,
                )
        
        messages.success(self.request, 'Stock take created successfully')
        return response
    
    def get_success_url(self):
        return reverse('inventory:stock_take_detail', kwargs={'pk': self.object.pk})

class StockTakeDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of stock take with item management.
    """
    model = StockTake
    template_name = 'inventory/stock_take/stock_take_detail.html'
    context_object_name = 'stock_take'
    
    @method_decorator(stock_take_permission)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_take = self.get_object()
        
        items = stock_take.items.select_related('product').order_by('product__name')
        
        # Calculate progress
        total_items = items.count()
        counted_items = items.exclude(actual_quantity__isnull=True).count()
        progress = (counted_items / total_items * 100) if total_items > 0 else 0
        
        # Calculate variances
        variances = []
        total_variance_value = Decimal('0')
        
        for item in items.exclude(actual_quantity__isnull=True):
            variance = item.variance
            variance_value = variance * item.product.cost_price
            total_variance_value += abs(variance_value)
            
            if variance != 0:
                variances.append({
                    'item': item,
                    'variance': variance,
                    'variance_value': variance_value,
                })
        
        context.update({
            'page_title': f'Stock Take: {stock_take.reference}',
            'items': items,
            'total_items': total_items,
            'counted_items': counted_items,
            'progress': round(progress, 1),
            'variances': sorted(variances, key=lambda x: abs(x['variance_value']), reverse=True),
            'total_variance_value': total_variance_value,
        })
        return context

@login_required
@stock_take_permission
@require_POST
def stock_take_complete_view(request, pk):
    """
    Complete a stock take and apply adjustments.
    """
    try:
        stock_take = get_object_or_404(StockTake, pk=pk)
        
        if stock_take.status != 'in_progress':
            messages.error(request, 'Only stock takes in progress can be completed')
            return redirect('inventory:stock_take_detail', pk=pk)
        
        # Check if all items have been counted
        uncounted_items = stock_take.items.filter(actual_quantity__isnull=True).count()
        if uncounted_items > 0:
            messages.error(request, f'{uncounted_items} items still need to be counted')
            return redirect('inventory:stock_take_detail', pk=pk)
        
        with transaction.atomic():
            adjustments_made = 0
            total_variance_value = Decimal('0')
            
            for item in stock_take.items.all():
                if item.variance != 0:
                    # Update stock levels
                    if stock_take.location:
                        # Specific location
                        stock_level, created = StockLevel.objects.get_or_create(
                            product=item.product,
                            location=stock_take.location,
                            defaults={'quantity': 0}
                        )
                        old_quantity = stock_level.quantity
                        stock_level.quantity = item.actual_quantity
                        stock_level.last_counted = timezone.now()
                        stock_level.save()
                    else:
                        # Overall stock
                        old_quantity = item.product.current_stock
                        item.product.current_stock = item.actual_quantity
                        item.product.last_stock_check = timezone.now()
                        item.product.save()
                    
                    # Create stock movement
                    StockMovement.objects.create(
                        product=item.product,
                        movement_type='adjustment',
                        quantity=item.variance,
                        from_location=stock_take.location if item.variance < 0 else None,
                        to_location=stock_take.location if item.variance > 0 else None,
                        previous_stock=old_quantity,
                        new_stock=item.actual_quantity,
                        reference=f"STOCK-TAKE-{stock_take.reference}",
                        notes=f"Stock take adjustment. Expected: {item.expected_quantity}, Actual: {item.actual_quantity}",
                        created_by=request.user,
                    )
                    
                    adjustments_made += 1
                    total_variance_value += abs(item.variance * item.product.cost_price)
            
            # Complete the stock take
            stock_take.status = 'completed'
            stock_take.completed_at = timezone.now()
            stock_take.total_variance_value = total_variance_value
            stock_take.save()
            
            messages.success(
                request,
                f'Stock take completed. {adjustments_made} adjustments made with total variance value of ${total_variance_value:.2f}'
            )
        
    except Exception as e:
        messages.error(request, f'Failed to complete stock take: {str(e)}')
    
    return redirect('inventory:stock_take_detail', pk=pk)

# =====================================
# DATA MANAGEMENT VIEWS
# =====================================

class DataExportView(LoginRequiredMixin, TemplateView):
    """Export inventory data"""
    template_name = 'inventory/data/data_export.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class DataImportView(LoginRequiredMixin, TemplateView):
    """Import inventory data"""
    template_name = 'inventory/data/data_import.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@login_required
@inventory_permission_required('admin')
def data_validation_view(request):
    """
    Comprehensive data validation and integrity checking.
    """
    try:
        validation_results = {
            'product_issues': [],
            'stock_issues': [],
            'pricing_issues': [],
            'supplier_issues': [],
        }
        
        # Product validation
        products = Product.objects.select_related('category', 'supplier')
        
        for product in products:
            issues = []
            
            # Check required fields
            if not product.sku:
                issues.append('Missing SKU')
            if not product.name:
                issues.append('Missing name')
            
            # Check pricing
            if product.cost_price <= 0:
                issues.append('Invalid cost price')
            if product.selling_price <= 0:
                issues.append('Invalid selling price')
            if product.selling_price < product.cost_price:
                issues.append('Selling price below cost price')
            
            # Check stock
            if product.current_stock < 0:
                issues.append('Negative stock')
            if product.reorder_level < 0:
                issues.append('Negative reorder level')
            
            # Check relationships
            if not product.category:
                issues.append('Missing category')
            if not product.supplier:
                issues.append('Missing supplier')
            
            if issues:
                validation_results['product_issues'].append({
                    'product': product,
                    'issues': issues,
                })
        
        # Stock level validation
        stock_levels = StockLevel.objects.select_related('product', 'location')
        
        for stock_level in stock_levels:
            issues = []
            
            if stock_level.quantity < 0:
                issues.append('Negative quantity')
            if stock_level.reserved_quantity < 0:
                issues.append('Negative reserved quantity')
            if stock_level.reserved_quantity > stock_level.quantity:
                issues.append('Reserved quantity exceeds total quantity')
            
            if issues:
                validation_results['stock_issues'].append({
                    'stock_level': stock_level,
                    'issues': issues,
                })
        
        # Check for duplicate SKUs
        from django.db.models import Count
        duplicate_skus = Product.objects.values('sku').annotate(
            count=Count('sku')
        ).filter(count__gt=1)
        
        for sku_data in duplicate_skus:
            products = Product.objects.filter(sku=sku_data['sku'])
            validation_results['product_issues'].append({
                'product': f"Duplicate SKU: {sku_data['sku']}",
                'issues': [f"Found {sku_data['count']} products with same SKU"],
                'products': list(products),
            })
        
        # Supplier validation
        suppliers = Supplier.objects.all()
        for supplier in suppliers:
            issues = []
            
            if not supplier.email and not supplier.phone:
                issues.append('No contact information')
            if supplier.average_lead_time_days < 0:
                issues.append('Negative lead time')
            if supplier.minimum_order_amount < 0:
                issues.append('Negative minimum order amount')
            
            if issues:
                validation_results['supplier_issues'].append({
                    'supplier': supplier,
                    'issues': issues,
                })
        
        return render(request, 'inventory/data/data_validation.html', {
            'page_title': 'Data Validation Report',
            'validation_results': validation_results,
            'total_issues': sum(len(issues) for issues in validation_results.values()),
        })
        
    except Exception as e:
        messages.error(request, f'Validation failed: {str(e)}')
        return redirect('inventory:dashboard')

@login_required
@inventory_permission_required('admin')
def data_cleanup_view(request):
    """
    Data cleanup and correction tools.
    """
    if request.method == 'POST':
        cleanup_type = request.POST.get('cleanup_type')
        
        try:
            if cleanup_type == 'fix_negative_stock':
                # Fix negative stock levels
                negative_products = Product.objects.filter(current_stock__lt=0)
                fixed_count = 0
                
                for product in negative_products:
                    product.current_stock = 0
                    product.save()
                    fixed_count += 1
                    
                    # Create adjustment record
                    StockMovement.objects.create(
                        product=product,
                        movement_type='adjustment',
                        quantity=abs(product.current_stock),
                        previous_stock=product.current_stock,
                        new_stock=0,
                        reference=f"CLEANUP-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        notes="Automated cleanup: Fixed negative stock",
                        created_by=request.user,
                    )
                
                messages.success(request, f'Fixed {fixed_count} products with negative stock')
                
            elif cleanup_type == 'remove_empty_categories':
                # Remove categories with no products
                empty_categories = Category.objects.filter(products__isnull=True, is_active=True)
                count = empty_categories.count()
                empty_categories.update(is_active=False)
                messages.success(request, f'Deactivated {count} empty categories')
                
            elif cleanup_type == 'fix_missing_barcodes':
                # Generate barcodes for products without them
                products_without_barcodes = Product.objects.filter(
                    Q(barcode='') | Q(barcode__isnull=True),
                    is_active=True
                )
                
                generated_count = 0
                for product in products_without_barcodes:
                    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
                    barcode = f"BT{product.id:06d}{timestamp[-4:]}"
                    
                    # Ensure uniqueness
                    counter = 1
                    original_barcode = barcode
                    while Product.objects.filter(barcode=barcode).exists():
                        barcode = f"{original_barcode}{counter:02d}"
                        counter += 1
                    
                    product.barcode = barcode
                    product.save()
                    generated_count += 1
                
                messages.success(request, f'Generated {generated_count} missing barcodes')
                
            elif cleanup_type == 'sync_stock_totals':
                # Sync product totals with stock levels
                synced_count = 0
                
                for product in Product.objects.filter(is_active=True):
                    total_stock = product.stock_levels.aggregate(
                        total=Sum('quantity')
                    )['total'] or 0
                    
                    if product.current_stock != total_stock:
                        product.current_stock = total_stock
                        product.save()
                        synced_count += 1
                
                messages.success(request, f'Synchronized {synced_count} product stock totals')
                
        except Exception as e:
            messages.error(request, f'Cleanup failed: {str(e)}')
    
    return render(request, 'inventory/data/data_cleanup.html', {
        'page_title': 'Data Cleanup Tools',
    })

@login_required
@inventory_permission_required('view')
def find_duplicates_view(request):
    """
    Find potential duplicate products.
    """
    try:
        # Find products with similar names
        from difflib import SequenceMatcher
        
        products = Product.objects.filter(is_active=True).order_by('name')
        potential_duplicates = []
        
        # Compare each product with others
        for i, product1 in enumerate(products):
            for product2 in products[i+1:]:
                # Calculate similarity
                similarity = SequenceMatcher(None, product1.name.lower(), product2.name.lower()).ratio()
                
                if similarity > 0.8:  # 80% similarity threshold
                    potential_duplicates.append({
                        'product1': product1,
                        'product2': product2,
                        'similarity': round(similarity * 100, 1),
                        'same_supplier': product1.supplier == product2.supplier,
                        'same_category': product1.category == product2.category,
                    })
        
        # Sort by similarity (highest first)
        potential_duplicates.sort(key=lambda x: x['similarity'], reverse=True)
        
        return render(request, 'inventory/data/find_duplicates.html', {
            'page_title': 'Find Duplicate Products',
            'potential_duplicates': potential_duplicates[:50],  # Limit to top 50
            'total_found': len(potential_duplicates),
        })
        
    except Exception as e:
        messages.error(request, f'Duplicate search failed: {str(e)}')
        return redirect('inventory:dashboard')

@login_required
@inventory_permission_required('view')
def import_templates_view(request):
    """Download import templates"""
    template_type = request.GET.get('type', 'products')
    
    if template_type == 'products':
        return product_import_template_view(request)
    
    # Add other template types as needed
    return HttpResponse('Template not found', status=404)

@login_required
@inventory_permission_required('admin')
def data_backup_view(request):
    """Backup inventory data"""
    # Implementation for data backup
    context = {
        'page_title': 'Data Backup',
    }
    return render(request, 'inventory/data/backup.html', context)

@login_required
@inventory_permission_required('admin')
def data_restore_view(request):
    """Restore inventory data"""
    # Implementation for data restore
    context = {
        'page_title': 'Data Restore',
    }
    return render(request, 'inventory/data/restore.html', context)

# =====================================
# MOBILE AND BARCODE FEATURES
# =====================================

class MobileDashboardView(LoginRequiredMixin, TemplateView):
    """
    Mobile-optimized inventory dashboard for warehouse staff.
    """
    template_name = 'inventory/mobile/mobile_dashboard.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Quick stats for mobile view
        low_stock_count = Product.objects.filter(
            current_stock__lte=F('reorder_level'),
            is_active=True
        ).count()
        
        pending_stock_takes = StockTake.objects.filter(
            status__in=['pending', 'in_progress']
        ).count()
        
        recent_movements = StockMovement.objects.select_related(
            'product'
        ).order_by('-created_at')[:10]
        
        context.update({
            'page_title': 'Mobile Inventory',
            'low_stock_count': low_stock_count,
            'pending_stock_takes': pending_stock_takes,
            'recent_movements': recent_movements,
            'is_mobile': True,
        })
        return context

class MobileStockCheckView(LoginRequiredMixin, TemplateView):
    """
    Quick stock check interface for mobile devices.
    """
    template_name = 'inventory/mobile/mobile_stock_check.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        search_term = self.request.GET.get('q', '').strip()
        product = None
        
        if search_term:
            # Try to find product by SKU or barcode first
            try:
                product = Product.objects.select_related(
                    'category', 'supplier'
                ).get(
                    Q(sku__iexact=search_term) | Q(barcode=search_term),
                    is_active=True
                )
            except Product.DoesNotExist:
                # Try partial name match
                products = Product.objects.filter(
                    name__icontains=search_term,
                    is_active=True
                ).select_related('category', 'supplier')[:5]
                
                if products.count() == 1:
                    product = products.first()
                elif products.count() > 1:
                    context['multiple_products'] = products
        
        if product:
            # Get stock levels by location
            stock_levels = product.stock_levels.select_related('location').all()
            
            context.update({
                'product': product,
                'stock_levels': stock_levels,
                'stock_status': get_stock_status(product),
            })
        
        context.update({
            'page_title': 'Stock Check',
            'search_term': search_term,
            'is_mobile': True,
        })
        return context

class BarcodeGeneratorView(LoginRequiredMixin, TemplateView):
    """
    Generate barcodes for products that don't have them.
    """
    template_name = 'inventory/barcode/barcode_generator.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get products without barcodes
        products_without_barcodes = Product.objects.filter(
            is_active=True,
            barcode__in=['', None]
        ).select_related('category', 'supplier').order_by('name')
        
        context.update({
            'page_title': 'Barcode Generator',
            'products_without_barcodes': products_without_barcodes,
            'total_products': products_without_barcodes.count(),
        })
        return context

class BarcodeScannerView(LoginRequiredMixin, TemplateView):
    """
    Barcode scanner interface for desktop/mobile.
    """
    template_name = 'inventory/barcode/barcode_scanner.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'page_title': 'Barcode Scanner',
            'scan_mode': self.request.GET.get('mode', 'lookup'),  # lookup, adjust, transfer
        })
        return context

class MobileBarcodeScannerView(LoginRequiredMixin, TemplateView):
    """Mobile-optimized barcode scanner"""
    template_name = 'inventory/barcodes/mobile_scanner.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@csrf_exempt
@require_http_methods(["POST"])
def mobile_sync_api(request):
    """API for mobile app synchronization"""
    try:
        data = json.loads(request.body)
        last_sync = data.get('last_sync')
        
        # Return changes since last sync
        sync_data = {
            'products': [],
            'stock_levels': [],
            'movements': [],
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(sync_data)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@require_http_methods(["GET"])
def mobile_offline_data_api(request):
    """API for mobile offline data"""
    # Return essential data for offline operation
    products = Product.objects.filter(is_active=True).values(
        'id', 'name', 'sku', 'current_stock', 'reorder_level'
    )[:100]  # Limit for mobile
    
    return JsonResponse({
        'products': list(products),
        'timestamp': timezone.now().isoformat(),
    })

@csrf_exempt
@require_http_methods(["POST"])
def mobile_upload_batch_api(request):
    """API for mobile batch uploads"""
    try:
        data = json.loads(request.body)
        batch_data = data.get('batch_data', [])
        
        processed_count = 0
        for item in batch_data:
            # Process each batch item
            # This could be stock adjustments, transfers, etc.
            processed_count += 1
        
        return JsonResponse({
            'success': True,
            'processed_count': processed_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@inventory_permission_required('edit')
@require_POST
def mobile_quick_adjust_view(request):
    """
    Quick stock adjustment from mobile device.
    """
    try:
        product_id = request.POST.get('product_id')
        location_id = request.POST.get('location_id')
        new_quantity = int(request.POST.get('new_quantity', 0))
        reason = request.POST.get('reason', 'Mobile adjustment')
        
        product = get_object_or_404(Product, id=product_id)
        
        with transaction.atomic():
            if location_id:
                location = get_object_or_404(Location, id=location_id)
                stock_level, created = StockLevel.objects.get_or_create(
                    product=product,
                    location=location,
                    defaults={'quantity': 0}
                )
                
                old_quantity = stock_level.quantity
                adjustment = new_quantity - old_quantity
                
                stock_level.quantity = new_quantity
                stock_level.last_counted = timezone.now()
                stock_level.save()
                
                # Update product total
                product.current_stock = product.stock_levels.aggregate(
                    total=Sum('quantity')
                )['total'] or 0
                
            else:
                old_quantity = product.current_stock
                adjustment = new_quantity - old_quantity
                product.current_stock = new_quantity
            
            product.last_stock_check = timezone.now()
            product.save()
            
            # Create movement record
            StockMovement.objects.create(
                product=product,
                movement_type='adjustment',
                quantity=adjustment,
                from_location=location if location_id and adjustment < 0 else None,
                to_location=location if location_id and adjustment > 0 else None,
                previous_stock=old_quantity,
                new_stock=new_quantity,
                reference=f"MOBILE-ADJ-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                notes=f"Mobile adjustment: {reason}",
                created_by=request.user
            )
            
        return JsonResponse({
            'success': True,
            'message': f'Stock updated: {product.name} adjusted by {adjustment}',
            'new_quantity': new_quantity,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@inventory_permission_required('edit')
def bulk_generate_barcodes_view(request):
    """
    Generate barcodes for multiple products at once.
    """
    if request.method == 'POST':
        try:
            product_ids = request.POST.getlist('product_ids')
            barcode_prefix = request.POST.get('prefix', 'BT')
            
            if not product_ids:
                messages.error(request, 'No products selected')
                return redirect('inventory:barcode_generator')
            
            generated_count = 0
            with transaction.atomic():
                for product_id in product_ids:
                    try:
                        product = Product.objects.get(id=product_id, is_active=True)
                        
                        if not product.barcode:
                            # Generate unique barcode
                            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
                            barcode = f"{barcode_prefix}{product.id:06d}{timestamp[-4:]}"
                            
                            # Ensure uniqueness
                            counter = 1
                            original_barcode = barcode
                            while Product.objects.filter(barcode=barcode).exists():
                                barcode = f"{original_barcode}{counter:02d}"
                                counter += 1
                            
                            product.barcode = barcode
                            product.save()
                            generated_count += 1
                            
                    except Product.DoesNotExist:
                        continue
            
            messages.success(request, f'Generated {generated_count} barcodes')
            
        except Exception as e:
            messages.error(request, f'Failed to generate barcodes: {str(e)}')
    
    return redirect('inventory:barcode_generator')

@login_required
@inventory_permission_required('view')
def print_barcode_labels_view(request):
    """
    Generate printable barcode labels.
    """
    try:
        product_ids = request.GET.getlist('product_id')
        
        if not product_ids:
            messages.error(request, 'No products selected for label printing')
            return redirect('inventory:product_list')
        
        products = Product.objects.filter(
            id__in=product_ids,
            is_active=True
        ).exclude(barcode__in=['', None])
        
        if not products:
            messages.error(request, 'No products with barcodes found')
            return redirect('inventory:product_list')
        
        # Generate barcode images
        label_data = []
        for product in products:
            try:
                # Generate barcode using python-barcode or similar
                from barcode import Code128
                from barcode.writer import ImageWriter
                
                code = Code128(product.barcode, writer=ImageWriter())
                barcode_buffer = BytesIO()
                code.write(barcode_buffer)
                barcode_b64 = base64.b64encode(barcode_buffer.getvalue()).decode()
                
                label_data.append({
                    'product': product,
                    'barcode_image': f'data:image/png;base64,{barcode_b64}',
                })
                
            except Exception as e:
                logger.error(f"Failed to generate barcode for {product.sku}: {str(e)}")
                continue
        
        return render(request, 'inventory/barcode/barcode_labels.html', {
            'page_title': 'Barcode Labels',
            'label_data': label_data,
        })
        
    except Exception as e:
        messages.error(request, f'Failed to generate labels: {str(e)}')
        return redirect('inventory:product_list')

@login_required
@inventory_permission_required('view')
def product_qr_code_api(request, product_id):
    """Generate QR code for a product"""
    try:
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Create QR code data
        qr_data = {
            'type': 'product',
            'sku': product.sku,
            'name': product.name,
            'brand': product.brand.name,
            'price': float(product.selling_price),
            'stock': product.total_stock,
            'url': request.build_absolute_uri(
                reverse('inventory:product_detail', args=[product.id])
            )
        }
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_data = base64.b64encode(buffer.getvalue()).decode()
        
        return JsonResponse({
            'success': True,
            'qr_code': img_data,
            'qr_data': qr_data
        })
        
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@inventory_permission_required('view')
def barcode_lookup_api(request):
    """
    API endpoint: Look up product by barcode.
    """
    try:
        barcode = request.GET.get('barcode', '').strip()
        
        if not barcode:
            return JsonResponse({'success': False, 'error': 'No barcode provided'})
        
        try:
            product = Product.objects.select_related(
                'category', 'supplier', 'brand'
            ).get(barcode=barcode, is_active=True)
            
            # Get stock levels
            stock_levels = []
            for stock_level in product.stock_levels.select_related('location'):
                stock_levels.append({
                    'location_id': stock_level.location.id,
                    'location_name': stock_level.location.name,
                    'quantity': stock_level.quantity,
                    'available_quantity': stock_level.available_quantity,
                })
            
            data = {
                'product_id': product.id,
                'sku': product.sku,
                'name': product.name,
                'description': product.description,
                'category': product.category.name if product.category else '',
                'supplier': product.supplier.name if product.supplier else '',
                'brand': product.brand.name if product.brand else '',
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'current_stock': product.current_stock,
                'reorder_level': product.reorder_level,
                'stock_status': get_stock_status(product),
                'stock_levels': stock_levels,
                'last_restocked': product.last_restocked_date.isoformat() if product.last_restocked_date else None,
            }
            
            return JsonResponse({'success': True, 'product': data})
            
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Product with barcode "{barcode}" not found'
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# =====================================
# QUICK ACCESS AND UTILITY VIEWS
# =====================================

class QuickAddProductView(LoginRequiredMixin, CreateView):
    """
    Quick product addition for mobile and fast entry.
    """
    model = Product
    fields = ['name', 'sku', 'category', 'supplier', 'cost_price', 'selling_price', 'current_stock']
    template_name = 'inventory/quick/quick_add_product.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Quick Add Product',
            'is_quick_form': True,
        })
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # Generate SKU if not provided
        if not form.instance.sku:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            form.instance.sku = f"QA-{timestamp}"
        
        messages.success(self.request, f'Product "{form.instance.name}" added successfully')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('inventory:quick_add_product')  # Stay on same page for continuous entry

class CurrencyListView(LoginRequiredMixin, ListView):
    """List all currencies and their exchange rates."""
    model = Currency
    template_name = 'inventory/configuration/currency_list.html'
    context_object_name = 'currencies'

    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return Currency.objects.order_by('code')

class CurrencyCreateView(LoginRequiredMixin, CreateView):
    """Create a new currency."""
    model = Currency
    form_class = CurrencyForm
    template_name = 'inventory/configuration/currency_form.html'
    success_url = reverse_lazy('inventory:currency_list')

    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Currency "{form.instance.code}" created successfully.')
        return super().form_valid(form)

class CurrencyUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing currency."""
    model = Currency
    form_class = CurrencyForm
    template_name = 'inventory/configuration/currency_form.html'
    success_url = reverse_lazy('inventory:currency_list')

    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Currency "{form.instance.code}" updated successfully.')
        return super().form_valid(form)

class CurrencyDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a currency (admin only)."""
    model = Currency
    template_name = 'inventory/configuration/currency_confirm_delete.html'
    success_url = reverse_lazy('inventory:currency_list')

    @method_decorator(inventory_permission_required('admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@login_required
@inventory_permission_required('view')
def quick_stock_check_view(request):
    """
    Quick stock level check by SKU or barcode.
    """
    result = None
    search_term = request.GET.get('q', '').strip()
    
    if search_term:
        try:
            product = Product.objects.select_related(
                'category', 'supplier'
            ).get(
                Q(sku__iexact=search_term) | Q(barcode=search_term),
                is_active=True
            )
            
            stock_levels = product.stock_levels.select_related('location').all()
            
            result = {
                'product': product,
                'stock_levels': stock_levels,
                'total_stock': product.current_stock,
                'stock_status': get_stock_status(product),
            }
            
        except Product.DoesNotExist:
            result = {
                'error': f'Product with SKU/Barcode "{search_term}" not found'
            }
        except Exception as e:
            result = {
                'error': f'Error: {str(e)}'
            }
    
    return render(request, 'inventory/quick/quick_stock_check.html', {
        'page_title': 'Quick Stock Check',
        'search_term': search_term,
        'result': result,
    })

@login_required
@inventory_permission_required('view')
def quick_cost_calculator_view(request):
    """
    Quick cost calculation tool.
    """
    calculation_result = None
    
    if request.GET.get('product_id') and request.GET.get('quantity'):
        try:
            product_id = int(request.GET.get('product_id'))
            quantity = int(request.GET.get('quantity', 1))
            
            product = get_object_or_404(Product, id=product_id)
            
            # Calculate costs
            base_cost = product.cost_price * quantity
            
            # Apply overhead factors
            overhead_factors = OverheadFactor.objects.filter(is_active=True)
            total_overhead_rate = sum(factor.percentage for factor in overhead_factors)
            overhead_cost = base_cost * (total_overhead_rate / 100)
            total_cost = base_cost + overhead_cost
            
            # Calculate margins
            selling_price = product.selling_price * quantity
            gross_margin = selling_price - base_cost
            net_margin = selling_price - total_cost
            
            calculation_result = {
                'product': product,
                'quantity': quantity,
                'base_cost': base_cost,
                'overhead_rate': total_overhead_rate,
                'overhead_cost': overhead_cost,
                'total_cost': total_cost,
                'selling_price': selling_price,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'gross_margin_percent': (gross_margin / selling_price * 100) if selling_price > 0 else 0,
                'net_margin_percent': (net_margin / selling_price * 100) if selling_price > 0 else 0,
            }
            
        except Exception as e:
            calculation_result = {
                'error': f'Calculation failed: {str(e)}'
            }
    
    # Get recent products for quick selection
    recent_products = Product.objects.filter(is_active=True).order_by('-created_at')[:20]
    
    return render(request, 'inventory/quick/quick_cost_calculator.html', {
        'page_title': 'Quick Cost Calculator',
        'calculation_result': calculation_result,
        'recent_products': recent_products,
    })

# =====================================
# DASHBOARD WIDGET ENDPOINTS
# =====================================

@login_required
@inventory_permission_required('view')
def global_inventory_search(request):
    """
    Global search across all inventory items.
    """
    try:
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 20))
        
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        # Search products
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query) |
            Q(description__icontains=query),
            is_active=True
        ).select_related('category', 'supplier')[:limit]
        
        results = []
        for product in products:
            results.append({
                'type': 'product',
                'id': product.id,
                'title': product.name,
                'subtitle': f"SKU: {product.sku} | Stock: {product.current_stock}",
                'category': product.category.name if product.category else '',
                'url': reverse('inventory:product_detail', args=[product.id]),
                'stock_status': get_stock_status(product),
            })
        
        # Search suppliers if query is longer
        if len(query) >= 3:
            suppliers = Supplier.objects.filter(
                name__icontains=query,
                is_active=True
            )[:5]
            
            for supplier in suppliers:
                results.append({
                    'type': 'supplier',
                    'id': supplier.id,
                    'title': supplier.name,
                    'subtitle': f"Products: {supplier.products.filter(is_active=True).count()}",
                    'url': reverse('inventory:supplier_detail', args=[supplier.id]),
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'total_found': len(results),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# =====================================
# SYSTEM ADMINISTRATION VIEWS
# =====================================

@login_required
@inventory_permission_required('admin')
def system_health_view(request):
    """System health monitoring"""
    context = {
        'page_title': 'System Health',
    }
    return render(request, 'inventory/admin/system_health.html', context)

@login_required
@inventory_permission_required('admin')
def performance_metrics_view(request):
    """Performance metrics"""
    context = {
        'page_title': 'Performance Metrics',
    }
    return render(request, 'inventory/admin/performance_metrics.html', context)

@login_required
@inventory_permission_required('admin')
def audit_log_view(request):
    """Audit log view"""
    context = {
        'page_title': 'Audit Log',
    }
    return render(request, 'inventory/admin/audit_log.html', context)

@login_required
@inventory_permission_required('admin')
def system_settings_view(request):
    """System settings"""
    context = {
        'page_title': 'System Settings',
    }
    return render(request, 'inventory/admin/system_settings.html', context)

@login_required
@inventory_permission_required('admin')
def system_maintenance_view(request):
    """System maintenance"""
    context = {
        'page_title': 'System Maintenance',
    }
    return render(request, 'inventory/admin/system_maintenance.html', context)

@login_required
@inventory_permission_required('admin')
def user_activity_view(request):
    """User activity monitoring"""
    context = {
        'page_title': 'User Activity',
    }
    return render(request, 'inventory/admin/user_activity.html', context)

@login_required
@inventory_permission_required('admin')
def permission_overview_view(request):
    """Permission overview"""
    context = {
        'page_title': 'Permission Overview',
    }
    return render(request, 'inventory/admin/permission_overview.html', context)

# =====================================
# SUPPORT VIEWS AND BUSINESS ENDPOINTS
# =====================================

@login_required
@inventory_permission_required('edit')
def product_duplicate_view(request, pk):
    """Duplicate an existing product"""
    original_product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        # Create duplicate
        duplicate = Product.objects.create(
            name=f"{original_product.name} (Copy)",
            sku=f"{original_product.sku}-COPY",
            description=original_product.description,
            category=original_product.category,
            brand=original_product.brand,
            supplier=original_product.supplier,
            cost_price=original_product.cost_price,
            selling_price=original_product.selling_price,
            unit_of_measure=original_product.unit_of_measure,
            weight=original_product.weight,
            dimensions=original_product.dimensions,
            reorder_level=original_product.reorder_level,
            minimum_order_quantity=original_product.minimum_order_quantity,
        )
        
        messages.success(request, f'Product "{duplicate.name}" created as a copy of "{original_product.name}"')
        return redirect('inventory:product_detail', pk=duplicate.pk)
    
    context = {
        'page_title': f'Duplicate Product: {original_product.name}',
        'product': original_product,
    }
    
    return render(request, 'inventory/products/product_duplicate.html', context)

@login_required
@cost_data_access
def product_cost_analysis_view(request, pk):
    """Detailed cost analysis for a product"""
    product = get_object_or_404(Product, pk=pk)
    
    # Calculate detailed costs
    base_cost = product.cost_price or Decimal('0.00')
    total_cost = PricingCalculator.calculate_product_total_cost(product)
    overhead_costs = total_cost - base_cost
    
    # Get overhead breakdown
    overhead_breakdown = []
    if product.category:
        overhead_factors = product.category.overhead_factors.filter(is_active=True)
        for factor in overhead_factors:
            if factor.calculation_method == 'percentage':
                factor_cost = base_cost * (factor.factor_value / 100)
            else:
                factor_cost = factor.factor_value
            
            overhead_breakdown.append({
                'factor': factor,
                'cost': factor_cost
            })
    
    # Calculate margins
    profit_margin = 0
    if product.selling_price and total_cost > 0:
        profit_margin = PricingCalculator.calculate_profit_margin(
            product.selling_price, total_cost
        )
    
    context = {
        'page_title': f'Cost Analysis: {product.name}',
        'product': product,
        'base_cost': base_cost,
        'total_cost': total_cost,
        'overhead_costs': overhead_costs,
        'overhead_breakdown': overhead_breakdown,
        'profit_margin': profit_margin,
    }
    
    return render(request, 'inventory/products/product_cost_analysis.html', context)

@login_required
@bulk_operation_permission
def product_bulk_update_view(request):
    """Bulk update products"""
    
    if request.method == 'POST':
        form = ProductBulkUpdateForm(request.POST)
        
        if form.is_valid():
            products = form.cleaned_data['products']
            action = form.cleaned_data['action']
            
            try:
                with transaction.atomic():
                    if action == 'update_prices':
                        # Handle price updates
                        adjustment_type = form.cleaned_data['price_adjustment_type']
                        adjustment_value = form.cleaned_data['price_adjustment_value']
                        
                        for product in products:
                            if adjustment_type == 'percentage':
                                if adjustment_value > 0:
                                    product.selling_price = product.selling_price * (1 + adjustment_value / 100)
                                else:
                                    product.selling_price = product.selling_price * (1 + adjustment_value / 100)
                            elif adjustment_type == 'fixed_amount':
                                product.selling_price = product.selling_price + adjustment_value
                            elif adjustment_type == 'set_price':
                                product.selling_price = adjustment_value
                            
                            product.save()
                    
                    elif action == 'update_category':
                        new_category = form.cleaned_data['new_category']
                        products.update(category=new_category)
                    
                    elif action == 'update_supplier':
                        new_supplier = form.cleaned_data['new_supplier']
                        products.update(supplier=new_supplier)
                    
                    elif action == 'activate':
                        products.update(is_active=True)
                    
                    elif action == 'deactivate':
                        products.update(is_active=False)
                
                messages.success(request, f'Bulk operation completed for {products.count()} products')
                
            except Exception as e:
                messages.error(request, f'Bulk operation failed: {str(e)}')
        
        return redirect('inventory:product_list')
    
    else:
        form = ProductBulkUpdateForm()
    
    context = {
        'page_title': 'Bulk Update Products',
        'form': form,
    }
    
    return render(request, 'inventory/products/product_bulk_update.html', context)

@login_required
@inventory_permission_required('view')
def product_import_template_view(request):
    """Download product import template"""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_import_template.csv"'
    
    writer = csv.writer(response)
    
    # Write header row
    writer.writerow([
        'Name', 'SKU', 'Description', 'Category', 'Brand', 'Supplier',
        'Cost Price', 'Selling Price', 'Current Stock', 'Reorder Level',
        'Unit of Measure', 'Weight', 'Dimensions'
    ])
    
    # Write sample data
    writer.writerow([
        'Sample Product', 'SAMPLE-001', 'This is a sample product',
        'Electronics', 'Sample Brand', 'Sample Supplier',
        '10.00', '15.00', '100', '10',
        'pcs', '0.5', '10x5x2'
    ])
    
    return response

@login_required
@inventory_permission_required('view')
def product_export_view(request):
    """Export products to CSV"""
    
    products = Product.objects.select_related(
        'category', 'brand', 'supplier'
    ).filter(is_active=True)
    
    # Apply filters if provided
    category = request.GET.get('category')
    if category:
        products = products.filter(category_id=category)
    
    supplier = request.GET.get('supplier')
    if supplier:
        products = products.filter(supplier_id=supplier)
    
    return ExportManager.export_products_to_csv(products)

@login_required
@inventory_permission_required('view')
def product_catalog_export_view(request):
    """Export product catalog with pricing"""
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="product_catalog.xlsx"'
    
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Product Catalog"
    
    # Headers
    headers = ['SKU', 'Name', 'Category', 'Brand', 'Supplier', 'Price', 'Stock', 'Description']
    worksheet.append(headers)
    
    # Data
    products = Product.objects.select_related(
        'category', 'brand', 'supplier'
    ).filter(is_active=True, selling_price__gt=0).order_by('category__name', 'name')
    
    for product in products:
        worksheet.append([
            product.sku,
            product.name,
            product.category.name if product.category else '',
            product.brand.name if product.brand else '',
            product.supplier.name if product.supplier else '',
            float(product.selling_price or 0),
            product.current_stock,
            product.description
        ])
    
    workbook.save(response)
    return response

@login_required
@inventory_permission_required('edit')
def update_exchange_rates_view(request):
    """Update currency exchange rates"""
    
    if request.method == 'POST':
        try:
            # Update exchange rates (placeholder - integrate with real API)
            updated_count = 0
            currencies = Currency.objects.filter(is_active=True).exclude(code='USD')
            
            for currency in currencies:
                # Placeholder - would fetch real rates from API
                # currency.exchange_rate_to_usd = fetch_exchange_rate(currency.code)
                # currency.save()
                updated_count += 1
            
            messages.success(request, f'Updated exchange rates for {updated_count} currencies')
            
        except Exception as e:
            messages.error(request, f'Failed to update exchange rates: {str(e)}')
    
    return redirect('inventory:currency_list')

@login_required
@inventory_permission_required('view')
def generate_reorder_recommendations_view(request):
    """Generate reorder recommendations"""
    
    recommendations = InventoryAnalytics.generate_reorder_recommendations()
    
    context = {
        'page_title': 'Reorder Recommendations',
        'recommendations': recommendations,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'inventory/reorder/reorder_recommendations.html', context)

@login_required
@inventory_permission_required('view')
def download_reorder_csv(request):
    """Download reorder list as CSV"""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reorder_list.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Product Name', 'Supplier', 'Current Stock', 'Reorder Level',
        'Recommended Quantity', 'Estimated Cost'
    ])
    
    recommendations = InventoryAnalytics.generate_reorder_recommendations()
    
    for rec in recommendations:
        product = rec['product']
        writer.writerow([
            product.sku,
            product.name,
            product.supplier.name if product.supplier else '',
            rec['current_stock'],
            rec['reorder_level'],
            rec['recommended_quantity'],
            float(rec['estimated_cost'])
        ])
    
    return response

@login_required
@bulk_operation_permission
def bulk_create_reorder_alerts_view(request):
    """Bulk create reorder alerts for low stock products"""
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                low_stock_products = get_low_stock_products()
                created_count = 0
                
                for product in low_stock_products:
                    # Check if alert already exists
                    existing_alert = ReorderAlert.objects.filter(
                        product=product,
                        is_active=True
                    ).first()
                    
                    if not existing_alert:
                        ReorderAlert.objects.create(
                            product=product,
                            supplier=product.supplier,
                            current_stock=product.current_stock,
                            reorder_level=product.reorder_level,
                            recommended_quantity=max(
                                product.reorder_level * 2 - product.current_stock,
                                product.minimum_order_quantity or 1
                            ),
                            priority='high' if product.current_stock == 0 else 'medium',
                            created_by=request.user
                        )
                        created_count += 1
                
                messages.success(request, f'Created {created_count} reorder alerts')
                
        except Exception as e:
            messages.error(request, f'Failed to create reorder alerts: {str(e)}')
    
    return redirect('inventory:reorder_alert_list')

@login_required
@inventory_permission_required('edit')
def acknowledge_reorder_alert_view(request, pk):
    """Acknowledge a reorder alert"""
    
    alert = get_object_or_404(ReorderAlert, pk=pk)
    alert.acknowledged_by = request.user
    alert.acknowledged_at = timezone.now()
    alert.save()
    
    messages.success(request, f'Reorder alert for {alert.product.name} acknowledged')
    return redirect('inventory:reorder_alert_list')

@login_required
@inventory_permission_required('edit')
def complete_reorder_alert_view(request, pk):
    """Mark reorder alert as completed"""
    
    alert = get_object_or_404(ReorderAlert, pk=pk)
    alert.is_active = False
    alert.completed_by = request.user
    alert.completed_at = timezone.now()
    alert.save()
    
    messages.success(request, f'Reorder alert for {alert.product.name} marked as completed')
    return redirect('inventory:reorder_alert_list')

@login_required
@purchase_order_permission
def create_purchase_order_from_alerts_view(request):
    """Create purchase orders from reorder alerts"""
    
    if request.method == 'POST':
        alert_ids = request.POST.getlist('alert_ids')
        
        if not alert_ids:
            messages.error(request, 'Please select alerts to create purchase orders from')
            return redirect('inventory:reorder_alert_list')
        
        try:
            with transaction.atomic():
                alerts = ReorderAlert.objects.filter(
                    id__in=alert_ids,
                    is_active=True
                ).select_related('product', 'supplier')
                
                # Group by supplier
                alerts_by_supplier = {}
                for alert in alerts:
                    supplier = alert.supplier
                    if supplier not in alerts_by_supplier:
                        alerts_by_supplier[supplier] = []
                    alerts_by_supplier[supplier].append(alert)
                
                created_pos = 0
                for supplier, supplier_alerts in alerts_by_supplier.items():
                    # Create purchase order
                    po = PurchaseOrder.objects.create(
                        supplier=supplier,
                        status='draft',
                        created_by=request.user
                    )
                    
                    # Add items
                    for alert in supplier_alerts:
                        PurchaseOrderItem.objects.create(
                            purchase_order=po,
                            product=alert.product,
                            quantity=alert.recommended_quantity,
                            unit_price=alert.product.cost_price or 0
                        )
                        
                        # Mark alert as completed
                        alert.is_active = False
                        alert.completed_by = request.user
                        alert.completed_at = timezone.now()
                        alert.save()
                    
                    created_pos += 1
                
                messages.success(request, f'Created {created_pos} purchase orders from selected alerts')
                
        except Exception as e:
            messages.error(request, f'Failed to create purchase orders: {str(e)}')
    
    return redirect('inventory:reorder_alert_list')

@login_required
@inventory_permission_required('view')  
def supplier_contact_view(request, pk):
    """Supplier contact information and communication"""
    
    supplier = get_object_or_404(Supplier, pk=pk)
    
    context = {
        'page_title': f'Contact: {supplier.name}',
        'supplier': supplier,
    }
    
    return render(request, 'inventory/suppliers/supplier_contact.html', context)

@login_required
def inventory_help_view(request):
    """Render static help documentation for inventory module."""
    return render(request, "inventory/help.html")

@login_required
def getting_started_guide(request):
    """Render getting started guide."""
    return render(request, "inventory/getting_started.html")

@login_required
def cost_calculation_guide(request):
    """Render cost calculation guide."""
    return render(request, "inventory/cost_calculation_guide.html")

@login_required
def api_documentation_view(request):
    """Render internal API documentation."""
    return render(request, "inventory/api_documentation.html")

@login_required
def quick_reorder_view(request):
    """List products that need reordering."""
    products = Product.objects.filter(
        is_active=True,
        total_stock__lt=F("reorder_level")
    ).select_related("supplier", "category")
    for product in products:
        product.reorder_qty = max(product.reorder_level * 2 - product.total_stock, 0)
    return render(request, "inventory/quick_reorder.html", {"products": products})

def _refresh_exchange_rates():
    """Fetch latest exchange rates from public API and update Currency table."""
    response = requests.get(
        "https://api.exchangerate.host/latest?base=USD", timeout=10
    )
    response.raise_for_status()
    data = response.json()
    rates = data.get("rates", {})
    updated = {}
    for currency in Currency.objects.filter(is_active=True):
        if currency.code == "USD":
            currency.exchange_rate_to_usd = Decimal("1")
        elif currency.code in rates:
            rate = Decimal(str(rates[currency.code]))
            currency.exchange_rate_to_usd = Decimal("1") / rate
        else:
            continue
        currency.save(update_fields=["exchange_rate_to_usd", "last_updated"])
        updated[currency.code] = float(currency.exchange_rate_to_usd)
    return updated

# --- API views ---

@login_required
@inventory_permission_required('view')
def low_stock_widget_api(request):
    """
    API endpoint for low stock dashboard widget.
    """
    try:
        low_stock_products = Product.objects.filter(
            current_stock__lte=F('reorder_level'),
            is_active=True
        ).select_related('category', 'supplier').order_by('current_stock')[:10]
        
        widget_data = []
        for product in low_stock_products:
            widget_data.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'current_stock': product.current_stock,
                'reorder_level': product.reorder_level,
                'shortage': product.reorder_level - product.current_stock,
                'category': product.category.name if product.category else '',
                'supplier': product.supplier.name if product.supplier else '',
                'url': reverse('inventory:product_detail', args=[product.id]),
            })
        
        return JsonResponse({
            'success': True,
            'data': widget_data,
            'total_low_stock': low_stock_products.count(),
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@inventory_permission_required('view')
def top_products_widget_api(request):
    """
    API endpoint for top products dashboard widget.
    """
    try:
        # Get top products by stock value
        products = Product.objects.filter(
            is_active=True,
            current_stock__gt=0
        ).annotate(
            stock_value=F('current_stock') * F('cost_price')
        ).order_by('-stock_value')[:10]
        
        widget_data = []
        for product in products:
            widget_data.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'current_stock': product.current_stock,
                'stock_value': float(product.current_stock * product.cost_price),
                'url': reverse('inventory:product_detail', args=[product.id]),
            })
        
        return JsonResponse({
            'success': True,
            'data': widget_data,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def update_exchange_rates_api(request):
    """Update currency exchange rates via API."""
    try:
        updated = _refresh_exchange_rates()
        return JsonResponse({"status": "success", "updated": updated})
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "message": str(exc)}, status=500
        )

@login_required
def currency_rates_api(request):
    """Return current exchange rates."""
    currencies = Currency.objects.filter(is_active=True).values(
        "code", "name", "exchange_rate_to_usd", "last_updated"
    )
    data = []
    for cur in currencies:
        cur["exchange_rate_to_usd"] = float(cur["exchange_rate_to_usd"])
        cur["last_updated"] = cur["last_updated"].isoformat()
        data.append(cur)
    return JsonResponse({"currencies": data})

@login_required
def currency_convert_api(request):
    """Convert amount between two currencies."""
    amount = request.GET.get("amount")
    from_code = request.GET.get("from")
    to_code = request.GET.get("to")
    if not all([amount, from_code, to_code]):
        return JsonResponse(
            {"status": "error", "message": "Missing parameters"}, status=400
        )
    try:
        amount = Decimal(amount)
        from_currency = Currency.objects.get(code=from_code)
        to_currency = Currency.objects.get(code=to_code)
        usd_amount = amount * from_currency.exchange_rate_to_usd
        target_amount = usd_amount / to_currency.exchange_rate_to_usd
        return JsonResponse(
            {"status": "success", "result": float(target_amount)}
        )
    except Currency.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Unknown currency"}, status=404
        )
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "message": str(exc)}, status=400
        )

@login_required
@require_POST
def bulk_price_update_api(request):
    """Apply percentage change to selling prices of multiple products."""
    try:
        payload = json.loads(request.body or "{}")
        ids = payload.get("product_ids", [])
        percentage = Decimal(str(payload.get("percentage", 0)))
    except (ValueError, TypeError):
        return JsonResponse({"status": "error", "message": "Invalid payload"}, status=400)
    if not ids or percentage == 0:
        return JsonResponse({"status": "error", "message": "Invalid parameters"}, status=400)
    multiplier = Decimal("1") + (percentage / 100)
    with transaction.atomic():
        products = Product.objects.filter(id__in=ids)
        for product in products:
            product.selling_price = product.selling_price * multiplier
            product.save(update_fields=["selling_price"])
    return JsonResponse({"status": "success", "updated": products.count()})

@login_required
def margin_analysis_api(request):
    """Provide margin information for products."""
    product_id = request.GET.get("product_id")
    if product_id:
        product = get_object_or_404(Product, pk=product_id)
        if product.selling_price:
            margin = (
                (product.selling_price - product.total_cost_price_usd)
                / product.selling_price
            ) * 100
        else:
            margin = Decimal("0")
        return JsonResponse(
            {
                "product": product.id,
                "margin_percent": float(margin.quantize(Decimal('0.01'))),
            }
        )
    qs = Product.objects.filter(is_active=True, selling_price__gt=0).annotate(
        margin_percent=100
        * (F("selling_price") - F("total_cost_price_usd"))
        / F("selling_price")
    )
    avg_margin = qs.aggregate(avg=Avg("margin_percent"))["avg"] or 0
    return JsonResponse({"average_margin_percent": float(avg_margin)})

@login_required
def category_performance_api(request):
    """Return performance metrics grouped by category."""
    categories = (
        Category.objects.filter(is_active=True)
        .annotate(
            product_count=Count("products", filter=Q(products__is_active=True)),
            stock_value=Sum(
                F("products__total_stock") * F("products__total_cost_price_usd")
            ),
        )
        .order_by("-stock_value")[:10]
        .values("id", "name", "product_count", "stock_value")
    )
    data = []
    for cat in categories:
        cat["stock_value"] = float(cat["stock_value"] or 0)
        data.append(cat)
    return JsonResponse({"categories": data})

@login_required
def check_stock_availability_api(request):
    """Check if enough stock is available for a product."""
    product_id = request.GET.get("product_id")
    quantity = int(request.GET.get("quantity", "0"))
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    available = product.total_stock >= quantity
    return JsonResponse(
        {
            "product_id": product.id,
            "requested": quantity,
            "available": available,
            "available_quantity": product.total_stock,
        }
    )

@login_required
def generate_barcode_api(request, product_id):
    """Generate barcode image for a product."""
    product = get_object_or_404(Product, pk=product_id)
    code = product.barcode or product.sku
    img_data = BarcodeManager.generate_barcode(code)
    if not img_data:
        return JsonResponse(
            {"status": "error", "message": "Failed to generate barcode"}, status=500
        )
    return JsonResponse({"status": "success", "barcode": img_data})

@login_required
@require_POST
def qr_code_scan_api(request):
    """Lookup product based on scanned QR code data."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = request.POST
    code = payload.get("code")
    if not code:
        return JsonResponse({"status": "error", "message": "No code provided"}, status=400)
    product = Product.objects.filter(qr_code=code).first()
    if not product:
        return JsonResponse({"status": "error", "message": "Product not found"}, status=404)
    return JsonResponse({"status": "success", "product": {"id": product.id, "name": product.name}})

@login_required
def reorder_recommendations_api(request):
    """Suggest reorder quantities for low stock products."""
    products = (
        Product.objects.filter(is_active=True, total_stock__lt=F("reorder_level"))
        .order_by("total_stock")
        .select_related("supplier")
    )
    recommendations = []
    for product in products:
        qty = max(product.reorder_level * 2 - product.total_stock, 0)
        recommendations.append(
            {
                "product_id": product.id,
                "name": product.name,
                "supplier": product.supplier.name,
                "recommended_quantity": qty,
            }
        )
    return JsonResponse({"recommendations": recommendations})

@login_required
def stock_levels_api(request):
    """Return current stock levels for active products."""
    products = Product.objects.filter(is_active=True).values(
        "id", "name", "total_stock", "reorder_level"
    )
    return JsonResponse({"products": list(products)})

@login_required
def stock_movements_api(request):
    """Return recent stock movement records."""
    movements = (
        StockMovement.objects.select_related("product")
        .order_by("-created_at")[:50]
        .values("id", "product__name", "movement_type", "quantity", "created_at")
    )
    data = [
        {
            "id": m["id"],
            "product": m["product__name"],
            "type": m["movement_type"],
            "quantity": m["quantity"],
            "date": m["created_at"].isoformat(),
        }
        for m in movements
    ]
    return JsonResponse({"movements": data})

@login_required
def stock_trends_api(request):
    """Return incoming/outgoing stock totals per day."""
    days = int(request.GET.get("days", 30))
    start = timezone.now() - timedelta(days=days)
    qs = StockMovement.objects.filter(created_at__gte=start)
    daily = (
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            incoming=Sum(
                "quantity", filter=Q(movement_type__in=["in", "purchase", "return"])
            ),
            outgoing=Sum(
                "quantity", filter=Q(movement_type__in=["out", "sale", "adjustment", "damaged"])
            ),
        )
        .order_by("day")
    )
    data = []
    for entry in daily:
        data.append(
            {
                "date": entry["day"].isoformat(),
                "incoming": entry["incoming"] or 0,
                "outgoing": abs(entry["outgoing"] or 0),
            }
        )
    return JsonResponse({"trends": data})

@login_required
def supplier_alerts_widget_api(request):
    """Return count of active reorder alerts grouped by supplier."""
    alerts = (
        ReorderAlert.objects.filter(status__in=["active", "acknowledged"])
        .values("product__supplier__id", "product__supplier__name")
        .annotate(alert_count=Count("id"))
        .order_by("-alert_count")[:5]
    )
    data = [
        {
            "supplier_id": a["product__supplier__id"],
            "supplier": a["product__supplier__name"],
            "alerts": a["alert_count"],
        }
        for a in alerts
    ]
    return JsonResponse({"suppliers": data})

@login_required
def supplier_country_analysis_api(request):
    """Return number of suppliers per country."""
    countries = (
        Supplier.objects.values("country__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    data = [{"country": c["country__name"], "suppliers": c["count"]} for c in countries]
    return JsonResponse({"countries": data})

@login_required
def dashboard_analytics_api(request):
    """Return basic dashboard metrics as JSON."""
    products = Product.objects.filter(is_active=True)
    totals = products.aggregate(
        total_stock_value=Sum(F("total_stock") * F("total_cost_price_usd")),
        low_stock=Count(
            "id",
            filter=Q(total_stock__lte=F("reorder_level"), total_stock__gt=0),
        ),
        out_of_stock=Count("id", filter=Q(total_stock=0)),
    )
    response = {
        "total_products": products.count(),
        "total_categories": Category.objects.filter(is_active=True).count(),
        "total_suppliers": Supplier.objects.filter(is_active=True).count(),
        "stock_value": float(totals["total_stock_value"] or 0),
        "low_stock": totals["low_stock"] or 0,
        "out_of_stock": totals["out_of_stock"] or 0,
    }
    return JsonResponse(response)

@login_required
def cost_trends_widget_api(request):
    """Return purchase cost totals grouped by month."""
    months = int(request.GET.get("months", 6))
    start = timezone.now() - timedelta(days=30 * months)
    qs = (
        StockMovement.objects.filter(
            created_at__gte=start, movement_type__in=["in", "purchase"]
        )
        .annotate(month=TruncDate("created_at"))
        .values("month")
        .annotate(
            total=Sum(F("quantity") * F("product__total_cost_price_usd"))
        )
        .order_by("month")
    )
    data = [
        {"date": entry["month"].isoformat(), "cost": float(entry["total"] or 0)}
        for entry in qs
    ]
    return JsonResponse({"cost_trends": data})

@login_required
@inventory_permission_required('view')
def quick_stats_api(request):
    """
    API endpoint for real-time dashboard statistics.
    
    Provides current inventory metrics for dashboard widgets and mobile apps.
    """
    try:
        stats = {
            'timestamp': timezone.now().isoformat(),
            'total_products': Product.objects.filter(is_active=True).count(),
            'low_stock_count': Product.objects.filter(
                is_active=True,
                current_stock__lte=F('reorder_level')
            ).count(),
            'out_of_stock_count': Product.objects.filter(
                is_active=True,
                current_stock=0
            ).count(),
            'total_stock_value': float(
                Product.objects.filter(is_active=True).aggregate(
                    total=Sum(F('current_stock') * F('cost_price'))
                )['total'] or 0
            ),
            'active_alerts': ReorderAlert.objects.filter(
                status__in=['active', 'acknowledged']
            ).count(),
            'pending_pos': PurchaseOrder.objects.filter(
                status__in=['draft', 'sent', 'acknowledged']
            ).count()
        }
        
        return JsonResponse({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error in quick stats API: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@inventory_permission_required('view')
def search_suggestions_api(request):
    """API for search suggestions"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) | Q(sku__icontains=query),
        is_active=True
    )[:10]
    
    suggestions = [
        {
            'id': product.id,
            'text': f"{product.name} ({product.sku})",
            'type': 'product'
        }
        for product in products
    ]
    
    return JsonResponse({'suggestions': suggestions})

# Initialize logging
logger.info("Inventory management views loaded successfully")
