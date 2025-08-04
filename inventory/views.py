# inventory/views.py - Comprehensive Inventory Management Views

"""
Django Views for Inventory Management System

This module provides complete view controllers for all inventory management
operations. The views are designed to work seamlessly with your existing
core system while providing advanced inventory functionality.

Key View Categories:
- Dashboard and analytics views
- Product management (CRUD and bulk operations)
- Stock management (adjustments, transfers, tracking)
- Supplier and category management
- Purchase order workflow
- Reporting and analytics
- API endpoints for real-time operations
- Integration endpoints for quote/CRM systems

All views include proper permission checking, error handling, and integration
with your existing notification and user management systems.
"""

import json
import csv
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.template.loader import render_to_string
from weasyprint import HTML

from django.utils.decorators import method_decorator
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, JsonResponse, HttpResponse, Http404
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count, Avg, F, Case, When
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.decorators import method_decorator
from openpyxl import Workbook

from .models import (
    Category, Supplier, Location, Product, StockLevel, StockMovement,
    StockTake, StockTakeItem, PurchaseOrder, PurchaseOrderItem, ReorderAlert
)
from .forms import (
    CategoryForm, SupplierForm, LocationForm, ProductForm, ProductSearchForm,
    StockAdjustmentForm, StockTransferForm, PurchaseOrderForm, PurchaseOrderItemForm,
    StockTakeForm, ProductBulkUpdateForm, InventoryReportForm
)
from .decorators import (
    inventory_permission_required, stock_adjustment_permission, location_access_required,
    purchase_order_permission, stock_take_permission, cost_data_access, bulk_operation_permission
)
from .utils import (
    calculate_available_stock, get_stock_status, calculate_stock_value,
    create_stock_movement, export_products_to_csv, import_products_from_csv,
    get_products_for_quote_system, check_stock_availability_for_quote,
    generate_stock_valuation_report, calculate_inventory_turnover
)

logger = logging.getLogger(__name__)

# =====================================
# DASHBOARD AND OVERVIEW VIEWS
# =====================================

class InventoryDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main inventory dashboard with comprehensive overview.
    
    Provides key metrics, alerts, and quick access to common operations.
    This is the command center for inventory management operations.
    """
    template_name = 'inventory/dashboard.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Key metrics
            context.update({
                'total_products': Product.objects.filter(is_active=True).count(),
                'total_stock_value': self._calculate_total_stock_value(),
                'low_stock_count': self._get_low_stock_count(),
                'out_of_stock_count': self._get_out_of_stock_count(),
                'pending_po_count': self._get_pending_po_count(),
                'active_alerts_count': self._get_active_alerts_count(),
            })
            
            # Recent activities
            context['recent_movements'] = self._get_recent_movements()
            context['recent_alerts'] = self._get_recent_alerts()
            context['pending_stock_takes'] = self._get_pending_stock_takes()
            
            # Quick stats for charts
            context['category_stats'] = self._get_category_stats()
            context['supplier_stats'] = self._get_supplier_stats()
            context['location_stats'] = self._get_location_stats()
            
            # Performance indicators
            context['performance_metrics'] = self._get_performance_metrics()
            
        except Exception as e:
            logger.error(f"Error loading dashboard data: {str(e)}")
            messages.error(self.request, "Error loading dashboard data.")
        
        return context
    
    def _calculate_total_stock_value(self):
        """Calculate total value of current stock"""
        try:
            return Product.objects.filter(is_active=True).aggregate(
                total_value=Sum(F('current_stock') * F('cost_price'))
            )['total_value'] or Decimal('0.00')
        except Exception:
            return Decimal('0.00')
    
    def _get_low_stock_count(self):
        """Get count of products with low stock"""
        return Product.objects.filter(
            is_active=True,
            current_stock__lte=F('reorder_level'),
            current_stock__gt=0
        ).count()
    
    def _get_out_of_stock_count(self):
        """Get count of products that are out of stock"""
        return Product.objects.filter(
            is_active=True,
            current_stock=0
        ).count()
    
    def _get_pending_po_count(self):
        """Get count of pending purchase orders"""
        return PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'acknowledged']
        ).count()
    
    def _get_active_alerts_count(self):
        """Get count of active reorder alerts"""
        return ReorderAlert.objects.filter(
            status__in=['active', 'acknowledged']
        ).count()
    
    def _get_recent_movements(self):
        """Get recent stock movements"""
        return StockMovement.objects.select_related(
            'product', 'created_by'
        ).order_by('-created_at')[:10]
    
    def _get_recent_alerts(self):
        """Get recent reorder alerts"""
        return ReorderAlert.objects.select_related(
            'product', 'suggested_supplier'
        ).order_by('-created_at')[:5]
    
    def _get_pending_stock_takes(self):
        """Get pending stock takes"""
        return StockTake.objects.filter(
            status__in=['planned', 'in_progress']
        ).order_by('scheduled_date')[:5]
    
    def _get_category_stats(self):
        """Get statistics by category"""
        return Category.objects.filter(is_active=True).annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            total_value=Sum(
                F('products__current_stock') * F('products__cost_price'),
                filter=Q(products__is_active=True)
            )
        ).order_by('-total_value')[:10]
    
    def _get_supplier_stats(self):
        """Get statistics by supplier"""
        return Supplier.objects.filter(is_active=True).annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            total_value=Sum(
                F('products__current_stock') * F('products__cost_price'),
                filter=Q(products__is_active=True)
            )
        ).order_by('-total_value')[:10]
    
    def _get_location_stats(self):
        """Get statistics by location"""
        return Location.objects.filter(is_active=True).annotate(
            product_count=Count('stock_levels__product', distinct=True),
            total_stock=Sum('stock_levels__quantity')
        ).order_by('-total_stock')
    
    def _get_performance_metrics(self):
        """Get key performance indicators"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        return {
            'movements_last_30_days': StockMovement.objects.filter(
                created_at__gte=thirty_days_ago
            ).count(),
            'pos_created_last_30_days': PurchaseOrder.objects.filter(
                created_at__gte=thirty_days_ago
            ).count(),
            'alerts_resolved_last_30_days': ReorderAlert.objects.filter(
                resolved_at__gte=thirty_days_ago
            ).count(),
        }

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

class InventoryOverviewView(LoginRequiredMixin, TemplateView):
    """Detailed inventory overview with filtering and analysis"""
    template_name = 'inventory/overview.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        category_id = self.request.GET.get('category')
        supplier_id = self.request.GET.get('supplier')
        location_id = self.request.GET.get('location')
        
        # Build base query
        products = Product.objects.filter(is_active=True).select_related(
            'category', 'supplier'
        )
        
        # Apply filters
        if category_id:
            products = products.filter(category_id=category_id)
        if supplier_id:
            products = products.filter(supplier_id=supplier_id)
        
        # Calculate metrics
        context.update({
            'products': products,
            'categories': Category.objects.filter(is_active=True),
            'suppliers': Supplier.objects.filter(is_active=True),
            'locations': Location.objects.filter(is_active=True),
            'selected_category': category_id,
            'selected_supplier': supplier_id,
            'selected_location': location_id,
            'total_value': calculate_stock_value(products),
            'total_quantity': products.aggregate(
                total=Sum('current_stock')
            )['total'] or 0
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

class ProductListView(LoginRequiredMixin, ListView):
    """
    Product listing with search, filtering, and pagination.
    
    Provides comprehensive product management interface with bulk operations.
    """
    model = Product
    template_name = 'inventory/product/product_list.html'
    context_object_name = 'products'
    paginate_by = 25
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        queryset = Product.objects.select_related(
            'category', 'supplier'
        ).order_by('name')
        
        # Handle search and filters
        search_form = ProductSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(sku__icontains=search) |
                    Q(description__icontains=search) |
                    Q(barcode__icontains=search)
                )
            
            category = search_form.cleaned_data.get('category')
            if category:
                queryset = queryset.filter(category=category)
            
            supplier = search_form.cleaned_data.get('supplier')
            if supplier:
                queryset = queryset.filter(supplier=supplier)
            
            stock_status = search_form.cleaned_data.get('stock_status')
            if stock_status == 'in_stock':
                queryset = queryset.filter(current_stock__gt=F('reorder_level'))
            elif stock_status == 'low_stock':
                queryset = queryset.filter(
                    current_stock__lte=F('reorder_level'),
                    current_stock__gt=0
                )
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(current_stock=0)
            
            is_active = search_form.cleaned_data.get('is_active')
            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)
            
            min_price = search_form.cleaned_data.get('min_price')
            if min_price:
                queryset = queryset.filter(selling_price__gte=min_price)
            
            max_price = search_form.cleaned_data.get('max_price')
            if max_price:
                queryset = queryset.filter(selling_price__lte=max_price)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ProductSearchForm(self.request.GET)
        context['can_edit'] = self.request.user.profile.user_type in [
            'sales_manager', 'blitzhub_admin', 'it_admin'
        ] if hasattr(self.request.user, 'profile') else False
        return context

class ProductDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed product view with stock information and analytics.
    
    Shows comprehensive product information including stock levels,
    movement history, supplier details, and performance metrics.
    """
    model = Product
    template_name = 'inventory/product/product_detail.html'
    context_object_name = 'product'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Stock levels by location
        context['stock_levels'] = StockLevel.objects.filter(
            product=product
        ).select_related('location')
        
        # Recent stock movements
        context['recent_movements'] = StockMovement.objects.filter(
            product=product
        ).select_related('created_by', 'from_location', 'to_location').order_by('-created_at')[:20]
        
        # Reorder alerts
        context['active_alerts'] = ReorderAlert.objects.filter(
            product=product,
            status__in=['active', 'acknowledged']
        )
        
        # Performance metrics
        context['performance'] = calculate_inventory_turnover(product, 365)
        
        # Stock adjustment form
        context['stock_adjustment_form'] = StockAdjustmentForm(
            initial={'product': product}
        )
        
        # Permission checks
        user_profile = getattr(self.request.user, 'profile', None)
        if user_profile:
            context['can_edit'] = user_profile.user_type in [
                'sales_manager', 'blitzhub_admin', 'it_admin'
            ]
            context['can_view_costs'] = user_profile.user_type in [
                'sales_manager', 'blitzhub_admin', 'it_admin'
            ]
        
        return context

class ProductCreateView(LoginRequiredMixin, CreateView):
    """Product creation view with intelligent defaults"""
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product/product_form.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        messages.success(
            self.request,
            f'Product "{form.instance.name}" created successfully.'
        )
        
        # Create notification for inventory managers
        from core.utils import create_bulk_notifications
        from django.contrib.auth.models import User
        
        managers = User.objects.filter(
            profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
            profile__is_active=True
        ).exclude(id=self.request.user.id)
        
        create_bulk_notifications(
            users=managers,
            title="New Product Added",
            message=f"Product '{form.instance.name}' ({form.instance.sku}) has been added to inventory",
            notification_type="info",
            action_url=form.instance.get_absolute_url(),
            action_text="View Product"
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('inventory:product_detail', kwargs={'pk': self.object.pk})

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    """Product update view with change tracking"""
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product/product_form.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        old_instance = Product.objects.get(pk=self.object.pk)
        response = super().form_valid(form)
        
        # Track significant changes
        changes = []
        if old_instance.selling_price != form.instance.selling_price:
            changes.append(f"Price: ${old_instance.selling_price} → ${form.instance.selling_price}")
        
        if old_instance.reorder_level != form.instance.reorder_level:
            changes.append(f"Reorder level: {old_instance.reorder_level} → {form.instance.reorder_level}")
        
        if changes:
            logger.info(f"Product {form.instance.sku} updated by {self.request.user.username}: {', '.join(changes)}")
        
        messages.success(
            self.request,
            f'Product "{form.instance.name}" updated successfully.'
        )
        
        return response
    
    def get_success_url(self):
        return reverse('inventory:product_detail', kwargs={'pk': self.object.pk})

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    """Product deletion view with safety checks"""
    model = Product
    template_name = 'inventory/product/product_confirm_delete.html'
    success_url = reverse_lazy('inventory:product_list')
    
    @method_decorator(inventory_permission_required('admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        
        # Check for dependencies
        if product.stock_movements.exists():
            messages.error(
                request,
                f'Cannot delete product "{product.name}" because it has stock movement history.'
            )
            return redirect('inventory:product_detail', pk=product.pk)
        
        if product.current_stock > 0:
            messages.error(
                request,
                f'Cannot delete product "{product.name}" because it has current stock.'
            )
            return redirect('inventory:product_detail', pk=product.pk)
        
        # Log deletion
        logger.warning(f"Product {product.sku} deleted by {request.user.username}")
        
        messages.success(
            request,
            f'Product "{product.name}" deleted successfully.'
        )
        
        return super().delete(request, *args, **kwargs)

class ProductSearchView(LoginRequiredMixin, ListView):
    template_name = "inventory/product/product_search.html"
    model = Product
    context_object_name = "products"
    paginate_by = 30

    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'supplier').all()
        search_form = ProductSearchForm(self.request.GET or None)
        
        if search_form.is_valid():
            data = search_form.cleaned_data
            search = data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(sku__icontains=search) |
                    Q(description__icontains=search) |
                    Q(barcode__icontains=search)
                )
            category = data.get('category')
            if category:
                queryset = queryset.filter(category=category)
            supplier = data.get('supplier')
            if supplier:
                queryset = queryset.filter(supplier=supplier)
            stock_status = data.get('stock_status')
            if stock_status == 'in_stock':
                queryset = queryset.filter(current_stock__gt=F('reorder_level'))
            elif stock_status == 'low_stock':
                queryset = queryset.filter(current_stock__lte=F('reorder_level'), current_stock__gt=0)
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(current_stock=0)
            is_active = data.get('is_active')
            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)
            min_price = data.get('min_price')
            if min_price is not None:
                queryset = queryset.filter(selling_price__gte=min_price)
            max_price = data.get('max_price')
            if max_price is not None:
                queryset = queryset.filter(selling_price__lte=max_price)
        else:
            # If not valid, show all products, or restrict further as you like.
            queryset = queryset.filter(is_active=True)
        
        # You can add more custom filtering logic here as needed.

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = ProductSearchForm(self.request.GET)
        context["categories"] = Category.objects.filter(is_active=True)
        context["suppliers"] = Supplier.objects.filter(is_active=True)
        context["can_edit"] = self.request.user.is_staff or (
            hasattr(self.request.user, 'profile') and self.request.user.profile.user_type in [
                'sales_manager', 'blitzhub_admin', 'it_admin'
            ]
        )
        return context

class ProductBulkImportView(LoginRequiredMixin, View):
    template_name = "inventory/product/product_import.html"

    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        # Just show the upload form and instructions
        return render(request, self.template_name)

    def post(self, request):
        file = request.FILES.get('import_file')
        if not file:
            messages.error(request, "No file uploaded.")
            return redirect('inventory:bulk_import')
        try:
            # Use your utility or similar import logic
            decoded = file.read().decode('utf-8').splitlines()
            import csv
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
                        'created_by': request.user,
                        'is_active': True,
                    }
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
            messages.success(request, f"Imported {created} new products, updated {updated}.")
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
        return redirect('inventory:bulk_import')

@login_required
@inventory_permission_required('edit')
def adjust_stock_view(request, pk):
    """
    Stock adjustment view for individual products.
    
    Allows authorized users to adjust stock levels with proper audit trail.
    """
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                adjustment_type = form.cleaned_data['adjustment_type']
                quantity = form.cleaned_data['quantity']
                reason = form.cleaned_data['reason']
                location = form.cleaned_data['location']
                notes = form.cleaned_data['notes']
                
                # Calculate actual adjustment quantity
                if adjustment_type == 'set':
                    actual_adjustment = quantity - product.current_stock
                elif adjustment_type == 'add':
                    actual_adjustment = quantity
                else:  # subtract
                    actual_adjustment = -quantity
                
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
                movement = create_stock_movement(
                    product=product,
                    movement_type='adjustment',
                    quantity=actual_adjustment,
                    reference=f"Manual adjustment: {reason}",
                    to_location=location if actual_adjustment > 0 else None,
                    from_location=location if actual_adjustment < 0 else None,
                    user=request.user,
                    notes=notes
                )
                
                messages.success(
                    request,
                    f'Stock adjusted for {product.name}. '
                    f'New stock level: {product.current_stock}'
                )
                
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
@inventory_permission_required('view')
def product_duplicate_view(request, pk):
    """Duplicate a product with new SKU"""
    original_product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, user=request.user)
        
        if form.is_valid():
            new_product = form.save(commit=False)
            new_product.created_by = request.user
            new_product.current_stock = 0  # Start with zero stock
            new_product.reserved_stock = 0
            new_product.total_sold = 0
            new_product.total_revenue = Decimal('0.00')
            new_product.last_sold_date = None
            new_product.last_restocked_date = None
            new_product.save()
            
            messages.success(
                request,
                f'Product duplicated successfully. New SKU: {new_product.sku}'
            )
            
            return redirect('inventory:product_detail', pk=new_product.pk)
    else:
        # Pre-populate form with original product data
        initial_data = {
            'name': f"{original_product.name} (Copy)",
            'category': original_product.category,
            'supplier': original_product.supplier,
            'description': original_product.description,
            'short_description': original_product.short_description,
            'product_type': original_product.product_type,
            'brand': original_product.brand,
            'model_number': original_product.model_number,
            'weight': original_product.weight,
            'dimensions': original_product.dimensions,
            'cost_price': original_product.cost_price,
            'selling_price': original_product.selling_price,
            'currency': original_product.currency,
            'reorder_level': original_product.reorder_level,
            'reorder_quantity': original_product.reorder_quantity,
            'max_stock_level': original_product.max_stock_level,
            'supplier_lead_time_days': original_product.supplier_lead_time_days,
            'minimum_order_quantity': original_product.minimum_order_quantity,
            'is_serialized': original_product.is_serialized,
            'is_perishable': original_product.is_perishable,
            'requires_quality_check': original_product.requires_quality_check
        }
        
        form = ProductForm(initial=initial_data, user=request.user)
    
    context = {
        'form': form,
        'original_product': original_product,
        'action': 'Duplicate'
    }
    
    return render(request, 'inventory/product/product_form.html', context)

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

# =====================================
# STOCK MANAGEMENT VIEWS
# =====================================

class StockOverviewView(LoginRequiredMixin, TemplateView):
    """Comprehensive stock overview and management"""
    template_name = 'inventory/stock/stock_overview.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Stock summary statistics
        context['total_stock_value'] = calculate_stock_value()
        context['total_products'] = Product.objects.filter(is_active=True).count()
        
        # Stock status breakdown
        context['stock_status_breakdown'] = {
            'in_stock': Product.objects.filter(
                is_active=True,
                current_stock__gt=F('reorder_level')
            ).count(),
            'low_stock': Product.objects.filter(
                is_active=True,
                current_stock__lte=F('reorder_level'),
                current_stock__gt=0
            ).count(),
            'out_of_stock': Product.objects.filter(
                is_active=True,
                current_stock=0
            ).count()
        }
        
        # Recent stock movements
        context['recent_movements'] = StockMovement.objects.select_related(
            'product', 'created_by'
        ).order_by('-created_at')[:20]
        
        # Location-wise stock distribution
        context['location_distribution'] = Location.objects.filter(
            is_active=True
        ).annotate(
            product_count=Count('stock_levels__product', distinct=True),
            total_stock=Sum('stock_levels__quantity'),
            total_value=Sum(
                F('stock_levels__quantity') * F('stock_levels__product__cost_price')
            )
        ).order_by('-total_value')
        
        return context

class StockMovementListView(LoginRequiredMixin, ListView):
    """Stock movement history with filtering"""
    model = StockMovement
    template_name = 'inventory/stock/stock_movements.html'
    context_object_name = 'movements'
    paginate_by = 50
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            'product', 'created_by', 'from_location', 'to_location'
        ).order_by('-created_at')
        
        # Apply filters
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        movement_type = self.request.GET.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter options
        context['movement_types'] = StockMovement.MOVEMENT_TYPES
        context['products'] = Product.objects.filter(is_active=True).order_by('name')
        
        # Current filter values
        context['current_filters'] = {
            'product': self.request.GET.get('product'),
            'movement_type': self.request.GET.get('movement_type'),
            'date_from': self.request.GET.get('date_from'),
            'date_to': self.request.GET.get('date_to')
        }
        
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

class StockTakeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StockTake
    template_name = 'inventory/stock/stock_take_list.html'
    context_object_name = 'stock_takes'
    paginate_by = 20
    permission_required = 'inventory.view_stocktake'

    def get_queryset(self):
        queryset = StockTake.objects.select_related('created_by', 'approved_by', 'location')\
                                    .order_by('-created_at')
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(reference__icontains=search)
        return queryset

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

# =====================================
# API ENDPOINTS
# =====================================

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
# PLACEHOLDER VIEWS FOR REMAINING FUNCTIONALITY
# =====================================

# These views would be fully implemented based on the patterns above

# Category Management Views
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category/category_list.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = 'inventory/category/category_detail.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category/category_form.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

# Supplier Management Views
class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier/supplier_list.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'inventory/supplier/supplier_detail.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier/supplier_form.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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

# Additional placeholder views would follow similar patterns...

# Quick action views
class QuickAddProductView(LoginRequiredMixin, CreateView):
    """Quick product addition for mobile and fast entry"""
    model = Product
    fields = ['name', 'sku', 'category', 'supplier', 'cost_price', 'selling_price']
    template_name = 'inventory/quick_add_product.html'
    
    @method_decorator(inventory_permission_required('edit'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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

# Help and utility views
class InventoryHelpView(LoginRequiredMixin, TemplateView):
    """Help and documentation for inventory system"""
    template_name = 'inventory/help.html'
    
    @method_decorator(inventory_permission_required('view'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class InventorySettingsView(LoginRequiredMixin, TemplateView):
    """Inventory system settings and configuration"""
    template_name = 'inventory/settings.html'
    
    @method_decorator(inventory_permission_required('admin'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

@login_required
@inventory_permission_required('view')
def product_export_view(request):
    """Export products to CSV"""
    try:
        products = Product.objects.filter(is_active=True).select_related('category', 'supplier')
        include_stock = request.GET.get('include_stock', 'true') == 'true'
        include_pricing = request.GET.get('include_pricing', 'true') == 'true'
        
        response = export_products_to_csv(products, include_stock, include_pricing)
        
        logger.info(f"Product export performed by {request.user.username}")
        return response
        
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        messages.error(request, f'Export failed: {str(e)}')
        return redirect('inventory:product_list')

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

# Initialize logging
logger.info("Inventory management views loaded successfully")
