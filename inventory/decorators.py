# inventory/decorators.py - Inventory-Specific Security and Validation Decorators

"""
Inventory Management Security Decorators

These decorators provide intelligent access control and business logic validation
specifically for inventory operations. They integrate seamlessly with your existing
core permission system while adding inventory-specific security rules.

The decorators understand complex inventory workflows like:
- Stock adjustment authorization levels
- Multi-location access control
- Purchase order approval workflows
- Stock take supervision requirements
- Supplier data access restrictions

This ensures that your inventory operations are secure, compliant, and follow
proper business processes while maintaining excellent user experience.
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

def inventory_permission_required(permission_level='view'):
    """
    Enhanced inventory permission decorator with business logic integration.
    
    This decorator checks inventory permissions while understanding the context
    of different inventory operations. It provides more granular control than
    generic permission checking.
    
    Args:
        permission_level: Required permission level ('view', 'edit', 'admin')
        
    Usage:
        @inventory_permission_required('edit')
        def adjust_stock(request, product_id):
            # User has inventory edit permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            from core.utils import check_app_permission
            
            # Check basic inventory permission
            if not check_app_permission(request.user, 'inventory', permission_level):
                logger.warning(
                    f"Inventory permission denied: User {request.user.username} "
                    f"lacks {permission_level} permission for inventory"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'You need {permission_level} permissions for inventory management',
                        'redirect': reverse('core:dashboard')
                    }, status=403)
                
                messages.error(
                    request, 
                    f'You need {permission_level} permissions to access inventory management.'
                )
                return redirect('core:dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def stock_adjustment_permission(max_adjustment_value=None):
    """
    Decorator for stock adjustment operations with value-based authorization.
    
    Different users may have different authorization levels for stock adjustments.
    For example, regular staff might adjust up to $1000 worth of stock, while
    managers can adjust unlimited amounts.
    
    Args:
        max_adjustment_value: Maximum value of stock adjustment allowed
        
    Usage:
        @stock_adjustment_permission(max_adjustment_value=1000)
        def adjust_stock_value(request, product_id):
            # User can adjust stock worth up to $1000
    """
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required('edit')
        def _wrapped_view(request, *args, **kwargs):
            user_profile = getattr(request.user, 'profile', None)
            
            # Admins and IT admins have unlimited adjustment authority
            if user_profile and user_profile.is_admin:
                return view_func(request, *args, **kwargs)
            
            # For POST requests, check the adjustment value
            if request.method == 'POST' and max_adjustment_value:
                try:
                    # Get product and calculate adjustment value
                    product_id = kwargs.get('product_id') or kwargs.get('pk')
                    if product_id:
                        from .models import Product
                        product = get_object_or_404(Product, id=product_id)
                        
                        adjustment_quantity = int(request.POST.get('adjustment_quantity', 0))
                        adjustment_value = abs(adjustment_quantity) * product.cost_price
                        
                        if adjustment_value > max_adjustment_value:
                            logger.warning(
                                f"Stock adjustment denied: User {request.user.username} "
                                f"attempted ${adjustment_value} adjustment (limit: ${max_adjustment_value})"
                            )
                            
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': f'Adjustment value ${adjustment_value:,.2f} exceeds your limit of ${max_adjustment_value:,.2f}',
                                    'requires_approval': True
                                }, status=403)
                            
                            messages.error(
                                request,
                                f'Stock adjustment of ${adjustment_value:,.2f} exceeds your authorization limit of ${max_adjustment_value:,.2f}. '
                                'Please request manager approval.'
                            )
                            return redirect('inventory:product_detail', pk=product.id)
                
                except (ValueError, TypeError) as e:
                    logger.error(f"Error validating stock adjustment: {str(e)}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Invalid adjustment value'
                        }, status=400)
                    
                    messages.error(request, 'Invalid adjustment value provided.')
                    return redirect('inventory:product_list')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def location_access_required(view_func):
    """
    Decorator to ensure user has access to specific inventory locations.
    
    Some users might only have access to certain locations (e.g., shop floor
    staff can't access warehouse inventory, regional managers only see their
    region's locations).
    
    Usage:
        @location_access_required
        def view_location_stock(request, location_id):
            # User has access to this specific location
    """
    @wraps(view_func)
    @inventory_permission_required('view')
    def _wrapped_view(request, *args, **kwargs):
        location_id = kwargs.get('location_id') or kwargs.get('pk')
        
        if location_id:
            from .models import Location
            
            try:
                location = get_object_or_404(Location, id=location_id)
                user_profile = getattr(request.user, 'profile', None)
                
                # Admins have access to all locations
                if user_profile and user_profile.is_admin:
                    return view_func(request, *args, **kwargs)
                
                # Check location-specific access rules
                # This could be expanded to include department-based restrictions
                # For now, we'll allow access to active locations for inventory users
                if not location.is_active:
                    logger.warning(
                        f"Access denied to inactive location {location.name} "
                        f"by user {request.user.username}"
                    )
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Access denied to inactive location'
                        }, status=403)
                    
                    messages.error(request, 'Access denied to inactive location.')
                    return redirect('inventory:location_list')
                
            except Exception as e:
                logger.error(f"Error checking location access: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Location access validation failed'
                    }, status=500)
                
                messages.error(request, 'Unable to validate location access.')
                return redirect('inventory:dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def purchase_order_permission(permission_type='view'):
    """
    Decorator for purchase order operations with workflow-based authorization.
    
    Purchase orders have complex approval workflows. This decorator ensures
    users can only perform actions they're authorized for based on PO status
    and business rules.
    
    Args:
        permission_type: Type of operation ('view', 'create', 'edit', 'approve')
        
    Usage:
        @purchase_order_permission('approve')
        def approve_purchase_order(request, po_id):
            # User can approve purchase orders
    """
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required('view')
        def _wrapped_view(request, *args, **kwargs):
            user_profile = getattr(request.user, 'profile', None)
            
            # Define authorization matrix
            authorization_rules = {
                'view': ['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin'],
                'create': ['sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin'],
                'edit': ['sales_manager', 'blitzhub_admin', 'it_admin'],
                'approve': ['sales_manager', 'blitzhub_admin', 'it_admin']
            }
            
            if not user_profile:
                logger.warning(f"User {request.user.username} has no profile for PO access")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'User profile required for purchase order access'
                    }, status=403)
                
                messages.error(request, 'User profile required for purchase order access.')
                return redirect('core:dashboard')
            
            user_type = user_profile.user_type
            allowed_user_types = authorization_rules.get(permission_type, [])
            
            if user_type not in allowed_user_types:
                logger.warning(
                    f"PO permission denied: User {request.user.username} with type {user_type} "
                    f"cannot {permission_type} purchase orders"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'You cannot {permission_type} purchase orders with your current role'
                    }, status=403)
                
                messages.error(
                    request,
                    f'You cannot {permission_type} purchase orders with your current role.'
                )
                return redirect('inventory:dashboard')
            
            # Additional checks for specific PO operations
            po_id = kwargs.get('po_id') or kwargs.get('pk')
            if po_id and permission_type in ['edit', 'approve']:
                from .models import PurchaseOrder
                
                try:
                    po = get_object_or_404(PurchaseOrder, id=po_id)
                    
                    # Check if PO can be edited/approved based on status
                    if permission_type == 'edit' and po.status in ['received', 'cancelled']:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': f'Cannot edit purchase order in {po.get_status_display()} status'
                            }, status=400)
                        
                        messages.error(
                            request,
                            f'Purchase order {po.po_number} cannot be edited as it is {po.get_status_display()}.'
                        )
                        return redirect('inventory:purchase_order_detail', pk=po.id)
                    
                    if permission_type == 'approve' and po.status != 'draft':
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': 'Only draft purchase orders can be approved'
                            }, status=400)
                        
                        messages.error(
                            request,
                            f'Purchase order {po.po_number} is not in draft status and cannot be approved.'
                        )
                        return redirect('inventory:purchase_order_detail', pk=po.id)
                
                except Exception as e:
                    logger.error(f"Error validating PO permission: {str(e)}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Purchase order validation failed'
                        }, status=500)
                    
                    messages.error(request, 'Unable to validate purchase order access.')
                    return redirect('inventory:dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def stock_take_permission(role_required='participant'):
    """
    Decorator for stock take operations with role-based authorization.
    
    Stock takes require different authorization levels:
    - Participants: Can count stock and record quantities
    - Supervisors: Can approve stock takes and resolve variances
    - Managers: Can create and manage stock take schedules
    
    Args:
        role_required: Required role ('participant', 'supervisor', 'manager')
        
    Usage:
        @stock_take_permission('supervisor')
        def approve_stock_take(request, stock_take_id):
            # User can supervise and approve stock takes
    """
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required('edit')
        def _wrapped_view(request, *args, **kwargs):
            user_profile = getattr(request.user, 'profile', None)
            
            if not user_profile:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'User profile required for stock take access'
                    }, status=403)
                
                messages.error(request, 'User profile required for stock take operations.')
                return redirect('core:dashboard')
            
            # Define role authorization
            role_permissions = {
                'participant': ['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin'],
                'supervisor': ['sales_manager', 'blitzhub_admin', 'it_admin'],
                'manager': ['sales_manager', 'blitzhub_admin', 'it_admin']
            }
            
            user_type = user_profile.user_type
            allowed_user_types = role_permissions.get(role_required, [])
            
            if user_type not in allowed_user_types:
                logger.warning(
                    f"Stock take permission denied: User {request.user.username} with type {user_type} "
                    f"cannot perform {role_required} operations"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'You cannot perform {role_required} operations for stock takes'
                    }, status=403)
                
                messages.error(
                    request,
                    f'You cannot perform {role_required} operations for stock takes with your current role.'
                )
                return redirect('inventory:dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

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

def bulk_operation_permission(operation_type, max_items=100):
    """
    Decorator for bulk operations with safety controls.
    
    Bulk operations can have significant business impact. This decorator
    ensures users have appropriate permissions and implements safety
    limits to prevent accidental mass changes.
    
    Args:
        operation_type: Type of bulk operation ('update', 'delete', 'adjust')
        max_items: Maximum number of items that can be processed
        
    Usage:
        @bulk_operation_permission('update', max_items=50)
        def bulk_update_prices(request):
            # User can bulk update up to 50 items
    """
    def decorator(view_func):
        @wraps(view_func)
        @inventory_permission_required('edit')
        def _wrapped_view(request, *args, **kwargs):
            user_profile = getattr(request.user, 'profile', None)
            
            # Check authorization for bulk operations
            if user_profile and user_profile.user_type not in ['sales_manager', 'blitzhub_admin', 'it_admin']:
                logger.warning(
                    f"Bulk operation denied: User {request.user.username} "
                    f"attempted {operation_type} operation without authorization"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'You do not have permission for bulk {operation_type} operations'
                    }, status=403)
                
                messages.error(
                    request,
                    f'You do not have permission for bulk {operation_type} operations.'
                )
                return redirect('inventory:dashboard')
            
            # Check item count limits for POST requests
            if request.method == 'POST':
                # Get selected items (common patterns)
                selected_items = request.POST.getlist('selected_items', [])
                item_ids = request.POST.getlist('item_ids', [])
                
                # Use whichever list has items
                items_to_process = selected_items or item_ids
                
                if len(items_to_process) > max_items:
                    logger.warning(
                        f"Bulk operation limit exceeded: User {request.user.username} "
                        f"attempted to process {len(items_to_process)} items (limit: {max_items})"
                    )
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': f'Cannot process more than {max_items} items at once. Selected: {len(items_to_process)}'
                        }, status=400)
                    
                    messages.error(
                        request,
                        f'Cannot process more than {max_items} items at once. You selected {len(items_to_process)} items.'
                    )
                    return redirect(request.get_full_path())
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def cost_data_access(view_func):
    """
    Decorator for cost and profit data access controls.
    
    Cost information and profit margins are sensitive business data.
    This decorator ensures only authorized personnel can view financial
    details of inventory items.
    
    Usage:
        @cost_data_access
        def view_product_costs(request, product_id):
            # User has access to cost and profit data
    """
    @wraps(view_func)
    @inventory_permission_required('view')
    def _wrapped_view(request, *args, **kwargs):
        user_profile = getattr(request.user, 'profile', None)
        
        if not user_profile:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'User profile required for cost data access'
                }, status=403)
            
            messages.error(request, 'User profile required for cost data access.')
            return redirect('core:dashboard')
        
        # Only managers and above can view cost data
        if user_profile.user_type not in ['sales_manager', 'blitzhub_admin', 'it_admin']:
            # Check if user has specific financial permissions
            from core.utils import check_app_permission
            
            if not check_app_permission(request.user, 'financial', 'view'):
                logger.warning(
                    f"Cost data access denied: User {request.user.username} "
                    f"lacks authorization for financial data"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'You do not have access to cost and profit information'
                    }, status=403)
                
                messages.error(
                    request,
                    'You do not have permission to view cost and profit information.'
                )
                return redirect('inventory:product_list')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Convenience decorators combining common permission patterns
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
