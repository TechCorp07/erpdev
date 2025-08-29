# inventory/decorators.py - Inventory-Specific Security and Validation Decorators

"""
The decorators understand complex inventory workflows like:
- Stock adjustment authorization levels
- Multi-location access control
- Purchase order approval workflows
- Stock take supervision requirements
- Supplier data access restrictions
"""

from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# =====================================
# BASE DECORATOR FACTORY
# =====================================

def create_inventory_decorator(permission_level, additional_checks=None, max_value=None):
    """
    Factory function to create inventory decorators with consistent patterns.
    
    Args:
        permission_level: Required permission level ('view', 'edit', 'admin')
        additional_checks: Optional list of additional check functions
        max_value: Optional maximum value limit for operations
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            from core.utils import has_app_permission
            
            # Check basic inventory permission
            if not has_app_permission(request.user, 'inventory', permission_level):
                logger.warning(
                    f"Inventory permission denied: User {request.user.username} "
                    f"lacks {permission_level} permission for inventory"
                )
                
                return _handle_permission_denied(request, permission_level)
            
            # Run additional checks if provided
            if additional_checks:
                for check_func in additional_checks:
                    result = check_func(request, *args, **kwargs)
                    if result is not True:
                        return result
            
            # Check value limits if specified
            if max_value and permission_level in ['edit', 'admin']:
                value_check = _check_value_limit(request, max_value)
                if value_check is not True:
                    return value_check
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator

def _handle_permission_denied(request, permission_level):
    """Handle permission denied responses consistently"""
    error_message = f'You need {permission_level} permissions to access inventory management.'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'error': error_message,
            'redirect': reverse('core:dashboard')
        }, status=403)
    
    messages.error(request, error_message)
    return redirect('core:dashboard')

def _check_value_limit(request, max_value):
    """Check if operation value exceeds limit"""
    # Extract value from request data
    value = None
    
    if request.method == 'POST':
        value = request.POST.get('value') or request.POST.get('amount') or request.POST.get('quantity')
    
    if value:
        try:
            value = Decimal(str(value))
            if value > max_value:
                error_msg = f'Operation value ({value}) exceeds maximum allowed ({max_value})'
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_msg
                    }, status=403)
                
                messages.error(request, error_msg)
                return redirect('inventory:dashboard')
        except (ValueError, TypeError):
            pass
    
    return True

# =====================================
# SPECIALIZED CHECK FUNCTIONS
# =====================================

def _check_location_access(request, *args, **kwargs):
    """Check if user has access to specific location"""
    location_id = kwargs.get('location_id') or request.POST.get('location_id')
    
    if location_id:
        from .models import Location
        try:
            location = Location.objects.get(id=location_id)
            # Add location-specific access logic here if needed
            # For now, just check if location exists and is active
            if not location.is_active:
                error_msg = 'This location is not active.'
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_msg
                    }, status=403)
                
                messages.error(request, error_msg)
                return redirect('inventory:location_list')
                
        except Location.DoesNotExist:
            error_msg = 'Location not found.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=404)
            
            messages.error(request, error_msg)
            return redirect('inventory:location_list')
    
    return True

def _check_product_access(request, *args, **kwargs):
    """Check if user has access to specific product"""
    product_id = kwargs.get('pk') or kwargs.get('product_id') or request.POST.get('product_id')
    
    if product_id:
        from .models import Product
        try:
            product = Product.objects.get(id=product_id)
            # Add product-specific access logic here if needed
            return True
        except Product.DoesNotExist:
            error_msg = 'Product not found.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=404)
            
            messages.error(request, error_msg)
            return redirect('inventory:product_list')
    
    return True

def _check_supplier_access(request, *args, **kwargs):
    """Check if user has access to specific supplier"""
    supplier_id = kwargs.get('pk') or kwargs.get('supplier_id')
    
    if supplier_id:
        from .models import Supplier
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            return True
        except Supplier.DoesNotExist:
            error_msg = 'Supplier not found.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=404)
            
            messages.error(request, error_msg)
            return redirect('inventory:supplier_list')
    
    return True

# =====================================
# MAIN DECORATOR DEFINITIONS
# =====================================

# Basic permission decorators
inventory_permission_required = lambda level: create_inventory_decorator(level)

# Location-specific decorators
def location_access_required(permission_level='view'):
    """Decorator for location-specific operations"""
    return create_inventory_decorator(
        permission_level, 
        additional_checks=[_check_location_access]
    )

# Stock operation decorators
def stock_adjustment_permission(max_adjustment_value=None):
    """Decorator for stock adjustment operations with optional value limits"""
    return create_inventory_decorator(
        'edit',
        additional_checks=[_check_product_access],
        max_value=max_adjustment_value
    )

def stock_take_permission(view_func):
    """Decorator for stock take operations"""
    return create_inventory_decorator('edit')(view_func)

# Purchase order decorators
def purchase_order_permission(view_func):
    """Decorator for purchase order operations"""
    return create_inventory_decorator('edit')(view_func)

# Bulk operation decorators
def bulk_operation_permission(view_func):
    """Decorator for bulk operations that affect multiple records"""
    return create_inventory_decorator('admin')(view_func)

# Cost and pricing decorators
def cost_data_access(view_func):
    """Decorator for accessing sensitive cost data"""
    return create_inventory_decorator('edit')(view_func)

# Supplier-specific decorators
def supplier_access_required(permission_level='view'):
    """Decorator for supplier-specific operations"""
    return create_inventory_decorator(
        permission_level,
        additional_checks=[_check_supplier_access]
    )

# =====================================
# CONVENIENCE DECORATORS
# =====================================

def inventory_manager_required(view_func):
    """Shortcut decorator for operations requiring inventory management authority"""
    return inventory_permission_required('admin')(view_func)

def stock_operations_required(view_func):
    """Shortcut decorator for stock manipulation operations"""
    return inventory_permission_required('edit')(view_func)

def read_only_inventory_access(view_func):
    """Shortcut decorator for read-only inventory access"""
    return inventory_permission_required('view')(view_func)

def high_value_stock_adjustment(view_func):
    """Shortcut decorator for high-value stock adjustments ($5000+ limit)"""
    return stock_adjustment_permission(max_adjustment_value=5000)(view_func)

def standard_stock_adjustment(view_func):
    """Shortcut decorator for standard stock adjustments ($1000 limit)"""
    return stock_adjustment_permission(max_adjustment_value=1000)(view_func)

def financial_data_access(view_func):
    """Shortcut decorator for financial/cost data access"""
    return cost_data_access(view_func)

# =====================================
# AJAX-SPECIFIC DECORATORS
# =====================================

def ajax_inventory_required(permission_level='view'):
    """Decorator specifically for AJAX inventory operations"""
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required(permission_level)
        def _wrapped_view(request, *args, **kwargs):
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'This endpoint requires AJAX requests'
                }, status=400)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator

# =====================================
# METHOD-SPECIFIC DECORATORS
# =====================================

def inventory_post_required(permission_level='edit'):
    """Decorator for POST-only inventory operations"""
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required(permission_level)
        def _wrapped_view(request, *args, **kwargs):
            if request.method != 'POST':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'POST method required'
                    }, status=405)
                
                messages.error(request, 'Invalid request method')
                return redirect('inventory:dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator

# =====================================
# VALIDATION DECORATORS
# =====================================

def validate_product_exists(view_func):
    """Decorator to validate product exists before processing"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        product_id = kwargs.get('pk') or kwargs.get('product_id')
        
        if product_id:
            from .models import Product
            try:
                product = get_object_or_404(Product, id=product_id)
                kwargs['product'] = product
            except Product.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Product not found'
                    }, status=404)
                
                messages.error(request, 'Product not found')
                return redirect('inventory:product_list')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

def supplier_data_access(view_func):
    """
    Decorator for supplier data access with confidentiality controls.
    
    Supplier information may contain sensitive commercial data that should
    only be accessible to authorized personnel. This decorator ensures
    proper access control for supplier-related operations.
    
    Usage:
        @supplier_data_access
        def view_supplier_pricing(request, supplier_id):
            # User has access to confidential supplier data
    """
    @wraps(view_func)
    @inventory_permission_required('view')
    def _wrapped_view(request, *args, **kwargs):
        user_profile = getattr(request.user, 'profile', None)
        
        if not user_profile:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'User profile required for supplier access'
                }, status=403)
            
            messages.error(request, 'User profile required for supplier operations.')
            return redirect('core:dashboard')
        
        # Define supplier data access levels
        # Regular employees can view basic supplier info
        # Managers and above can view pricing and commercial terms
        user_type = user_profile.user_type
        
        # Check if accessing detailed/sensitive supplier data
        if 'pricing' in request.path or 'cost' in request.path or 'terms' in request.path:
            if user_type not in ['sales_manager', 'blitzhub_admin', 'it_admin']:
                logger.warning(
                    f"Supplier data access denied: User {request.user.username} "
                    f"attempted to access sensitive supplier information"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'You do not have access to detailed supplier information'
                    }, status=403)
                
                messages.error(
                    request,
                    'You do not have permission to access detailed supplier information.'
                )
                return redirect('inventory:supplier_list')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
