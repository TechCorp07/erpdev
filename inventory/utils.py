# inventory/utils.py - Comprehensive Inventory Management Utilities

"""
Utility Functions for Inventory Management

This module provides essential utility functions that power the inventory
management system. These functions handle complex business logic, calculations,
and integrations while maintaining consistency and reliability.

Key Functionality:
- Stock level calculations and validations
- Automated reorder point management
- Cost and pricing calculations
- Report generation utilities
- Data import/export functions
- Integration helpers for quote and CRM systems
- Performance analytics and forecasting
- Barcode and QR code generation
"""

import csv
import io
import logging
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction, models
from django.db.models import Q, Sum, Count, Avg, F, Case, When
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

# =====================================
# STOCK CALCULATION UTILITIES
# =====================================

def calculate_available_stock(product, location=None):
    """
    Calculate available stock for a product, optionally at a specific location.
    
    Available stock = Current stock - Reserved stock
    
    Args:
        product: Product instance
        location: Optional Location instance for location-specific calculation
        
    Returns:
        int: Available stock quantity
    """
    try:
        if location:
            from .models import StockLevel
            stock_level = StockLevel.objects.filter(
                product=product, location=location
            ).first()
            
            if stock_level:
                return max(0, stock_level.quantity - stock_level.reserved_quantity)
            return 0
        else:
            return max(0, product.current_stock - product.reserved_stock)
            
    except Exception as e:
        logger.error(f"Error calculating available stock for {product.sku}: {str(e)}")
        return 0

def get_stock_status(product):
    """
    Determine stock status for a product based on current levels.
    
    Args:
        product: Product instance
        
    Returns:
        str: Stock status ('in_stock', 'low_stock', 'out_of_stock', 'discontinued')
    """
    try:
        if not product.is_active:
            return 'discontinued'
        
        available = calculate_available_stock(product)
        
        if available <= 0:
            return 'out_of_stock'
        elif available <= product.reorder_level:
            return 'low_stock'
        else:
            return 'in_stock'
            
    except Exception as e:
        logger.error(f"Error determining stock status for {product.sku}: {str(e)}")
        return 'unknown'

def calculate_stock_value(products=None, location=None, cost_basis='current'):
    """
    Calculate total stock value for products.
    
    Args:
        products: QuerySet of products (default: all active products)
        location: Optional location filter
        cost_basis: 'current', 'average', or 'fifo' (default: 'current')
        
    Returns:
        Decimal: Total stock value
    """
    try:
        from .models import Product, StockLevel
        
        if products is None:
            products = Product.objects.filter(is_active=True)
        
        total_value = Decimal('0.00')
        
        for product in products:
            if location:
                stock_level = StockLevel.objects.filter(
                    product=product, location=location
                ).first()
                quantity = stock_level.quantity if stock_level else 0
            else:
                quantity = product.current_stock
            
            # For now, use current cost price
            # In the future, this could be enhanced for FIFO/average costing
            unit_cost = product.cost_price
            total_value += quantity * unit_cost
        
        return total_value
        
    except Exception as e:
        logger.error(f"Error calculating stock value: {str(e)}")
        return Decimal('0.00')

def calculate_reorder_recommendations(category=None, supplier=None):
    """
    Calculate reorder recommendations based on current stock levels and usage patterns.
    
    Args:
        category: Optional category filter
        supplier: Optional supplier filter
        
    Returns:
        List[Dict]: List of reorder recommendations
    """
    try:
        from .models import Product, ReorderAlert
        
        # Build base query
        products = Product.objects.filter(is_active=True)
        
        if category:
            products = products.filter(category=category)
        if supplier:
            products = products.filter(supplier=supplier)
        
        # Find products that need reordering
        products_needing_reorder = products.filter(
            current_stock__lte=F('reorder_level')
        ).order_by('current_stock')
        
        recommendations = []
        
        for product in products_needing_reorder:
            # Check if there's already an active alert
            existing_alert = ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).exists()
            
            if not existing_alert:
                # Calculate recommended order quantity
                recommended_qty = calculate_optimal_order_quantity(product)
                
                # Calculate estimated cost
                estimated_cost = recommended_qty * product.cost_price
                
                # Determine priority
                stock_ratio = product.current_stock / max(product.reorder_level, 1)
                if stock_ratio <= 0:
                    priority = 'critical'
                elif stock_ratio <= 0.5:
                    priority = 'high'
                elif stock_ratio <= 0.8:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                recommendations.append({
                    'product': product,
                    'current_stock': product.current_stock,
                    'reorder_level': product.reorder_level,
                    'recommended_quantity': recommended_qty,
                    'estimated_cost': estimated_cost,
                    'priority': priority,
                    'supplier': product.supplier,
                    'lead_time_days': product.supplier_lead_time_days
                })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error calculating reorder recommendations: {str(e)}")
        return []

def calculate_optimal_order_quantity(product):
    """
    Calculate optimal order quantity using Economic Order Quantity (EOQ) principles.
    
    Args:
        product: Product instance
        
    Returns:
        int: Recommended order quantity
    """
    try:
        # Get basic parameters
        annual_demand = estimate_annual_demand(product)
        ordering_cost = Decimal('50.00')  # Estimated ordering cost per PO
        holding_cost_rate = Decimal('0.20')  # 20% annual holding cost
        
        if annual_demand > 0 and product.cost_price > 0:
            # EOQ formula: sqrt(2 * D * S / H)
            # Where D = annual demand, S = ordering cost, H = holding cost per unit
            holding_cost_per_unit = product.cost_price * holding_cost_rate
            
            import math
            eoq = math.sqrt(
                (2 * float(annual_demand) * float(ordering_cost)) / 
                float(holding_cost_per_unit)
            )
            
            # Round to nearest whole number and ensure minimum order quantity
            recommended_qty = max(
                int(round(eoq)),
                product.minimum_order_quantity,
                product.reorder_quantity
            )
            
            return recommended_qty
        else:
            # Fallback to reorder quantity if we can't calculate EOQ
            return product.reorder_quantity
            
    except Exception as e:
        logger.error(f"Error calculating optimal order quantity for {product.sku}: {str(e)}")
        return product.reorder_quantity

def estimate_annual_demand(product):
    """
    Estimate annual demand based on historical sales data.
    
    Args:
        product: Product instance
        
    Returns:
        int: Estimated annual demand
    """
    try:
        from .models import StockMovement
        
        # Calculate demand based on last 90 days of sales
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        sales_movements = StockMovement.objects.filter(
            product=product,
            movement_type='sale',
            created_at__gte=ninety_days_ago,
            quantity__lt=0  # Negative quantity for outgoing movements
        ).aggregate(total_sold=Sum('quantity'))
        
        total_sold = abs(sales_movements['total_sold'] or 0)
        
        if total_sold > 0:
            # Extrapolate to annual demand
            daily_demand = total_sold / 90
            annual_demand = daily_demand * 365
            return int(round(annual_demand))
        else:
            # No recent sales data, use a conservative estimate
            return max(product.reorder_quantity * 4, 12)  # Quarterly orders
            
    except Exception as e:
        logger.error(f"Error estimating annual demand for {product.sku}: {str(e)}")
        return product.reorder_quantity * 4


# =====================================
# PRICING AND COST UTILITIES
# =====================================

def calculate_selling_price(cost_price, markup_percentage, currency='USD'):
    """
    Calculate selling price based on cost and markup percentage.
    
    Args:
        cost_price: Decimal cost price
        markup_percentage: Decimal markup percentage (e.g., 30.00 for 30%)
        currency: Currency code for rounding rules
        
    Returns:
        Decimal: Calculated selling price
    """
    try:
        if cost_price <= 0:
            return Decimal('0.00')
        
        markup_multiplier = 1 + (markup_percentage / 100)
        selling_price = cost_price * markup_multiplier
        
        # Round to appropriate precision based on currency
        if currency in ['USD', 'EUR', 'GBP']:
            return selling_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        elif currency == 'ZWG':
            # Zimbabwe Gold might need different rounding
            return selling_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            return selling_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
    except Exception as e:
        logger.error(f"Error calculating selling price: {str(e)}")
        return Decimal('0.00')

def calculate_profit_margin(cost_price, selling_price):
    """
    Calculate profit margin percentage.
    
    Args:
        cost_price: Decimal cost price
        selling_price: Decimal selling price
        
    Returns:
        Decimal: Profit margin percentage
    """
    try:
        if cost_price <= 0:
            return Decimal('0.00')
        
        profit = selling_price - cost_price
        margin_percentage = (profit / cost_price) * 100
        
        return margin_percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
    except Exception as e:
        logger.error(f"Error calculating profit margin: {str(e)}")
        return Decimal('0.00')

def apply_bulk_price_update(products, update_type, value, user=None):
    """
    Apply bulk price updates to multiple products.
    
    Args:
        products: QuerySet of products to update
        update_type: 'markup', 'percentage_increase', 'fixed_increase', 'set_price'
        value: Decimal value for the update
        user: User performing the update
        
    Returns:
        int: Number of products updated
    """
    try:
        updated_count = 0
        
        with transaction.atomic():
            for product in products:
                old_price = product.selling_price
                
                if update_type == 'markup':
                    # Apply markup percentage to cost price
                    product.selling_price = calculate_selling_price(
                        product.cost_price, value
                    )
                elif update_type == 'percentage_increase':
                    # Increase current price by percentage
                    multiplier = 1 + (value / 100)
                    product.selling_price = old_price * multiplier
                elif update_type == 'fixed_increase':
                    # Add fixed amount to current price
                    product.selling_price = old_price + value
                elif update_type == 'set_price':
                    # Set specific price
                    product.selling_price = value
                
                # Ensure price is not negative
                product.selling_price = max(product.selling_price, Decimal('0.01'))
                
                product.save(update_fields=['selling_price'])
                
                # Log the price change
                logger.info(
                    f"Price updated for {product.sku}: {old_price} -> {product.selling_price} "
                    f"by {user.username if user else 'System'}"
                )
                
                updated_count += 1
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in bulk price update: {str(e)}")
        return 0


# =====================================
# STOCK MOVEMENT UTILITIES
# =====================================

def create_stock_movement(product, movement_type, quantity, reference, 
                         from_location=None, to_location=None, user=None, 
                         unit_cost=None, notes=""):
    """
    Create a stock movement record with proper validation and stock updates.
    
    Args:
        product: Product instance
        movement_type: Type of movement ('in', 'out', 'adjustment', etc.)
        quantity: Quantity moved (positive for in, negative for out)
        reference: Reference number or description
        from_location: Source location (optional)
        to_location: Destination location (optional)
        user: User performing the movement
        unit_cost: Cost per unit (optional)
        notes: Additional notes
        
    Returns:
        StockMovement: Created movement record
    """
    try:
        from .models import StockMovement
        
        with transaction.atomic():
            # Record current stock before movement
            previous_stock = product.current_stock
            
            # Calculate new stock level
            new_stock = max(0, previous_stock + quantity)
            
            # Create movement record
            movement = StockMovement.objects.create(
                product=product,
                movement_type=movement_type,
                quantity=quantity,
                from_location=from_location,
                to_location=to_location,
                reference=reference,
                previous_stock=previous_stock,
                new_stock=new_stock,
                unit_cost=unit_cost,
                total_cost=abs(quantity) * unit_cost if unit_cost else None,
                notes=notes,
                created_by=user
            )
            
            # Update product stock
            product.current_stock = new_stock
            if movement_type in ['sale', 'out']:
                product.total_sold = (product.total_sold or 0) + abs(quantity)
                product.last_sold_date = timezone.now()
            elif movement_type in ['purchase', 'in']:
                product.last_restocked_date = timezone.now()
            
            product.save()
            
            # Update location-specific stock levels
            update_location_stock_levels(movement)
            
            return movement
            
    except Exception as e:
        logger.error(f"Error creating stock movement: {str(e)}")
        raise ValidationError(f"Failed to create stock movement: {str(e)}")

def update_location_stock_levels(movement):
    """
    Update location-specific stock levels based on stock movement.
    
    Args:
        movement: StockMovement instance
    """
    try:
        from .models import StockLevel
        
        # Update from_location
        if movement.from_location and movement.quantity < 0:
            stock_level, created = StockLevel.objects.get_or_create(
                product=movement.product,
                location=movement.from_location,
                defaults={'quantity': 0, 'reserved_quantity': 0}
            )
            stock_level.quantity = max(0, stock_level.quantity + movement.quantity)
            stock_level.save()
        
        # Update to_location
        if movement.to_location and movement.quantity > 0:
            stock_level, created = StockLevel.objects.get_or_create(
                product=movement.product,
                location=movement.to_location,
                defaults={'quantity': 0, 'reserved_quantity': 0}
            )
            stock_level.quantity += movement.quantity
            stock_level.save()
            
    except Exception as e:
        logger.error(f"Error updating location stock levels: {str(e)}")

def transfer_stock_between_locations(product, from_location, to_location, 
                                   quantity, reference, user=None, notes=""):
    """
    Transfer stock between locations with proper validation.
    
    Args:
        product: Product instance
        from_location: Source location
        to_location: Destination location
        quantity: Quantity to transfer
        reference: Transfer reference
        user: User performing transfer
        notes: Transfer notes
        
    Returns:
        Tuple[StockMovement, StockMovement]: (outgoing, incoming) movements
    """
    try:
        from .models import StockLevel
        
        with transaction.atomic():
            # Check available stock at from_location
            from_stock = StockLevel.objects.filter(
                product=product, location=from_location
            ).first()
            
            if not from_stock or from_stock.available_quantity < quantity:
                raise ValidationError(
                    f"Insufficient stock at {from_location.name}. "
                    f"Available: {from_stock.available_quantity if from_stock else 0}, "
                    f"Required: {quantity}"
                )
            
            # Create outgoing movement
            outgoing = create_stock_movement(
                product=product,
                movement_type='transfer',
                quantity=-quantity,
                reference=reference,
                from_location=from_location,
                to_location=None,
                user=user,
                notes=f"Transfer to {to_location.name}. {notes}"
            )
            
            # Create incoming movement
            incoming = create_stock_movement(
                product=product,
                movement_type='transfer',
                quantity=quantity,
                reference=reference,
                from_location=None,
                to_location=to_location,
                user=user,
                notes=f"Transfer from {from_location.name}. {notes}"
            )
            
            return outgoing, incoming
            
    except Exception as e:
        logger.error(f"Error transferring stock: {str(e)}")
        raise ValidationError(f"Stock transfer failed: {str(e)}")


# =====================================
# IMPORT/EXPORT UTILITIES
# =====================================

def export_products_to_csv(products, include_stock=True, include_pricing=True):
    """
    Export products to CSV format.
    
    Args:
        products: QuerySet of products to export
        include_stock: Include stock information
        include_pricing: Include pricing information
        
    Returns:
        HttpResponse: CSV file response
    """
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        
        writer = csv.writer(response)
        
        # Define headers
        headers = [
            'SKU', 'Name', 'Category', 'Supplier', 'Description',
            'Brand', 'Model Number', 'Barcode'
        ]
        
        if include_stock:
            headers.extend([
                'Current Stock', 'Available Stock', 'Reserved Stock',
                'Reorder Level', 'Reorder Quantity'
            ])
        
        if include_pricing:
            headers.extend([
                'Cost Price', 'Selling Price', 'Currency', 'Profit Margin %'
            ])
        
        headers.extend(['Is Active', 'Created Date', 'Last Updated'])
        
        writer.writerow(headers)
        
        # Write product data
        for product in products.select_related('category', 'supplier'):
            row = [
                product.sku,
                product.name,
                product.category.name,
                product.supplier.name,
                product.description,
                product.brand,
                product.model_number,
                product.barcode
            ]
            
            if include_stock:
                row.extend([
                    product.current_stock,
                    product.available_stock,
                    product.reserved_stock,
                    product.reorder_level,
                    product.reorder_quantity
                ])
            
            if include_pricing:
                row.extend([
                    product.cost_price,
                    product.selling_price,
                    product.currency,
                    product.profit_margin_percentage
                ])
            
            row.extend([
                'Yes' if product.is_active else 'No',
                product.created_at.strftime('%Y-%m-%d'),
                product.updated_at.strftime('%Y-%m-%d')
            ])
            
            writer.writerow(row)
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting products to CSV: {str(e)}")
        raise

def import_products_from_csv(csv_file, user=None, update_existing=False):
    """
    Import products from CSV file.
    
    Args:
        csv_file: Uploaded CSV file
        user: User performing the import
        update_existing: Whether to update existing products
        
    Returns:
        Dict: Import results with counts and errors
    """
    try:
        from .models import Product, Category, Supplier
        
        results = {
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'errors': [],
            'warnings': []
        }
        
        # Read CSV file
        csv_data = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        with transaction.atomic():
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
                results['total_rows'] += 1
                
                try:
                    # Extract data from row
                    sku = row.get('SKU', '').strip()
                    name = row.get('Name', '').strip()
                    category_name = row.get('Category', '').strip()
                    supplier_name = row.get('Supplier', '').strip()
                    
                    if not all([sku, name, category_name, supplier_name]):
                        results['errors'].append(
                            f"Row {row_num}: Missing required fields (SKU, Name, Category, Supplier)"
                        )
                        continue
                    
                    # Find or create category
                    category, created = Category.objects.get_or_create(
                        name=category_name,
                        defaults={'slug': category_name.lower().replace(' ', '-')}
                    )
                    
                    # Find or create supplier
                    supplier, created = Supplier.objects.get_or_create(
                        name=supplier_name,
                        defaults={
                            'supplier_code': f"SUP-{supplier_name[:3].upper()}",
                            'email': f"info@{supplier_name.lower().replace(' ', '')}.com"
                        }
                    )
                    
                    # Check if product exists
                    existing_product = Product.objects.filter(sku=sku).first()
                    
                    if existing_product and not update_existing:
                        results['warnings'].append(
                            f"Row {row_num}: Product {sku} already exists (skipped)"
                        )
                        continue
                    
                    # Prepare product data
                    product_data = {
                        'name': name,
                        'category': category,
                        'supplier': supplier,
                        'description': row.get('Description', ''),
                        'brand': row.get('Brand', ''),
                        'model_number': row.get('Model Number', ''),
                        'barcode': row.get('Barcode', ''),
                        'cost_price': Decimal(row.get('Cost Price', '0') or '0'),
                        'selling_price': Decimal(row.get('Selling Price', '0') or '0'),
                        'reorder_level': int(row.get('Reorder Level', '10') or '10'),
                        'reorder_quantity': int(row.get('Reorder Quantity', '50') or '50'),
                        'is_active': row.get('Is Active', 'Yes').lower() in ['yes', 'true', '1'],
                        'created_by': user
                    }
                    
                    if existing_product:
                        # Update existing product
                        for field, value in product_data.items():
                            if field != 'created_by':  # Don't change creator
                                setattr(existing_product, field, value)
                        existing_product.save()
                        results['updated'] += 1
                    else:
                        # Create new product
                        product_data['sku'] = sku
                        Product.objects.create(**product_data)
                        results['created'] += 1
                
                except Exception as e:
                    results['errors'].append(f"Row {row_num}: {str(e)}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error importing products from CSV: {str(e)}")
        raise ValidationError(f"Import failed: {str(e)}")


# =====================================
# INTEGRATION UTILITIES
# =====================================

def get_products_for_quote_system(search_term=None, category=None, supplier=None, limit=50):
    """
    Get products formatted for quote system integration.
    
    Args:
        search_term: Optional search term
        category: Optional category filter
        supplier: Optional supplier filter
        limit: Maximum number of results
        
    Returns:
        List[Dict]: Products formatted for quote system
    """
    try:
        from .models import Product
        
        products = Product.objects.filter(is_active=True).select_related(
            'category', 'supplier'
        )
        
        # Apply filters
        if search_term:
            products = products.filter(
                Q(name__icontains=search_term) |
                Q(sku__icontains=search_term) |
                Q(description__icontains=search_term)
            )
        
        if category:
            products = products.filter(category=category)
        
        if supplier:
            products = products.filter(supplier=supplier)
        
        # Limit results
        products = products[:limit]
        
        # Format for quote system
        formatted_products = []
        for product in products:
            formatted_products.append({
                'id': product.id,
                'sku': product.sku,
                'name': product.name,
                'description': product.short_description or product.description[:100],
                'category': product.category.name,
                'supplier': product.supplier.name,
                'cost_price': float(product.cost_price),
                'selling_price': float(product.selling_price),
                'currency': product.currency,
                'current_stock': product.current_stock,
                'available_stock': product.available_stock,
                'stock_status': get_stock_status(product),
                'lead_time_days': product.supplier_lead_time_days,
                'minimum_quantity': product.minimum_order_quantity,
                'barcode': product.barcode
            })
        
        return formatted_products
        
    except Exception as e:
        logger.error(f"Error getting products for quote system: {str(e)}")
        return []

def check_stock_availability_for_quote(quote_items):
    """
    Check stock availability for quote items.
    
    Args:
        quote_items: List of dicts with 'product_id' and 'quantity'
        
    Returns:
        Dict: Availability status for each item
    """
    try:
        from .models import Product
        
        availability = {}
        
        for item in quote_items:
            product_id = item.get('product_id')
            requested_qty = item.get('quantity', 0)
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
                available_qty = calculate_available_stock(product)
                
                availability[product_id] = {
                    'product_name': product.name,
                    'sku': product.sku,
                    'requested_quantity': requested_qty,
                    'available_quantity': available_qty,
                    'can_fulfill': available_qty >= requested_qty,
                    'shortage': max(0, requested_qty - available_qty),
                    'stock_status': get_stock_status(product),
                    'lead_time_days': product.supplier_lead_time_days
                }
                
            except Product.DoesNotExist:
                availability[product_id] = {
                    'error': 'Product not found or inactive'
                }
        
        return availability
        
    except Exception as e:
        logger.error(f"Error checking stock availability: {str(e)}")
        return {}

def reserve_stock_for_quote(quote_items, quote_reference, user=None):
    """
    Reserve stock for quote items.
    
    Args:
        quote_items: List of dicts with 'product_id' and 'quantity'
        quote_reference: Quote reference number
        user: User creating the reservation
        
    Returns:
        Dict: Reservation results
    """
    try:
        from .models import Product
        
        results = {
            'success': True,
            'reservations': [],
            'errors': []
        }
        
        with transaction.atomic():
            for item in quote_items:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 0)
                
                try:
                    product = Product.objects.get(id=product_id, is_active=True)
                    
                    if product.reserve_stock(quantity):
                        results['reservations'].append({
                            'product_id': product_id,
                            'sku': product.sku,
                            'quantity_reserved': quantity
                        })
                        
                        # Log the reservation
                        logger.info(
                            f"Reserved {quantity} units of {product.sku} for quote {quote_reference}"
                        )
                    else:
                        results['errors'].append(
                            f"Insufficient stock to reserve {quantity} units of {product.sku}"
                        )
                        results['success'] = False
                        
                except Product.DoesNotExist:
                    results['errors'].append(f"Product {product_id} not found")
                    results['success'] = False
        
        return results
        
    except Exception as e:
        logger.error(f"Error reserving stock for quote: {str(e)}")
        return {'success': False, 'errors': [str(e)]}


# =====================================
# REPORTING UTILITIES
# =====================================

def generate_stock_valuation_report(location=None, category=None, as_of_date=None):
    """
    Generate stock valuation report.
    
    Args:
        location: Optional location filter
        category: Optional category filter
        as_of_date: Optional date for historical valuation
        
    Returns:
        Dict: Valuation report data
    """
    try:
        from .models import Product, Category
        
        # Build base query
        products = Product.objects.filter(is_active=True).select_related(
            'category', 'supplier'
        )
        
        if category:
            products = products.filter(category=category)
        
        # Calculate valuations
        report_data = {
            'as_of_date': as_of_date or timezone.now().date(),
            'location': location.name if location else 'All Locations',
            'category': category.name if category else 'All Categories',
            'total_products': products.count(),
            'total_quantity': 0,
            'total_value': Decimal('0.00'),
            'categories': [],
            'products': []
        }
        
        # Group by category
        categories = Category.objects.filter(
            products__in=products
        ).distinct().order_by('name')
        
        for cat in categories:
            cat_products = products.filter(category=cat)
            cat_quantity = sum(p.current_stock for p in cat_products)
            cat_value = sum(p.current_stock * p.cost_price for p in cat_products)
            
            report_data['categories'].append({
                'name': cat.name,
                'product_count': cat_products.count(),
                'total_quantity': cat_quantity,
                'total_value': cat_value
            })
            
            report_data['total_quantity'] += cat_quantity
            report_data['total_value'] += cat_value
        
        # Add detailed product information
        for product in products.order_by('category__name', 'name'):
            product_value = product.current_stock * product.cost_price
            
            report_data['products'].append({
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'supplier': product.supplier.name,
                'quantity': product.current_stock,
                'cost_price': product.cost_price,
                'total_value': product_value,
                'stock_status': get_stock_status(product)
            })
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error generating stock valuation report: {str(e)}")
        return {}

def generate_abc_analysis(criteria='revenue', period_days=365):
    """
    Generate ABC analysis for inventory classification.
    
    Args:
        criteria: 'revenue', 'quantity', or 'profit'
        period_days: Analysis period in days
        
    Returns:
        Dict: ABC analysis results
    """
    try:
        from .models import Product, StockMovement
        
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Calculate metrics for each product
        products_data = []
        
        for product in Product.objects.filter(is_active=True):
            # Get sales movements for the period
            sales_movements = StockMovement.objects.filter(
                product=product,
                movement_type='sale',
                created_at__gte=start_date,
                quantity__lt=0
            )
            
            total_quantity = abs(sales_movements.aggregate(
                total=Sum('quantity')
            )['total'] or 0)
            
            total_revenue = sales_movements.filter(
                unit_cost__isnull=False
            ).aggregate(
                total=Sum(F('quantity') * F('unit_cost') * -1)
            )['total'] or Decimal('0.00')
            
            # Calculate profit (simplified)
            total_profit = total_quantity * (product.selling_price - product.cost_price)
            
            if criteria == 'revenue':
                value = total_revenue
            elif criteria == 'quantity':
                value = total_quantity
            else:  # profit
                value = total_profit
            
            products_data.append({
                'product': product,
                'value': value,
                'quantity': total_quantity,
                'revenue': total_revenue,
                'profit': total_profit
            })
        
        # Sort by criteria value
        products_data.sort(key=lambda x: x['value'], reverse=True)
        
        # Calculate cumulative percentages
        total_value = sum(item['value'] for item in products_data)
        cumulative_value = 0
        
        for item in products_data:
            cumulative_value += item['value']
            item['cumulative_percentage'] = (cumulative_value / total_value * 100) if total_value > 0 else 0
        
        # Classify into A, B, C categories
        a_products = []
        b_products = []
        c_products = []
        
        for item in products_data:
            if item['cumulative_percentage'] <= 70:
                item['classification'] = 'A'
                a_products.append(item)
            elif item['cumulative_percentage'] <= 90:
                item['classification'] = 'B'
                b_products.append(item)
            else:
                item['classification'] = 'C'
                c_products.append(item)
        
        return {
            'criteria': criteria,
            'period_days': period_days,
            'total_products': len(products_data),
            'a_products': len(a_products),
            'b_products': len(b_products),
            'c_products': len(c_products),
            'analysis_data': products_data,
            'summary': {
                'A': {'count': len(a_products), 'percentage': 70},
                'B': {'count': len(b_products), 'percentage': 20},
                'C': {'count': len(c_products), 'percentage': 10}
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating ABC analysis: {str(e)}")
        return {}


# =====================================
# BARCODE AND QR CODE UTILITIES
# =====================================

def generate_product_barcode(product, format='CODE128'):
    """
    Generate barcode for a product.
    
    Args:
        product: Product instance
        format: Barcode format ('CODE128', 'EAN13', etc.)
        
    Returns:
        bytes: Barcode image data
    """
    try:
        # This would integrate with a barcode library like python-barcode
        # For now, return a placeholder
        logger.info(f"Generating {format} barcode for product {product.sku}")
        return None
        
    except Exception as e:
        logger.error(f"Error generating barcode: {str(e)}")
        return None

def validate_barcode_format(barcode, format_type='AUTO'):
    """
    Validate barcode format.
    
    Args:
        barcode: Barcode string
        format_type: Expected format or 'AUTO' for auto-detection
        
    Returns:
        bool: True if valid
    """
    try:
        if not barcode:
            return False
        
        # Basic validation patterns
        patterns = {
            'EAN13': r'^\d{13}$',
            'EAN8': r'^\d{8}$',
            'UPC': r'^\d{12}$',
            'CODE128': r'^[A-Za-z0-9\-\.\s\$\/\+%]+$'
        }
        
        if format_type == 'AUTO':
            # Try to detect format
            for fmt, pattern in patterns.items():
                if re.match(pattern, barcode):
                    return True
            return False
        else:
            pattern = patterns.get(format_type)
            if pattern:
                return bool(re.match(pattern, barcode))
            return False
        
    except Exception as e:
        logger.error(f"Error validating barcode: {str(e)}")
        return False


# =====================================
# PERFORMANCE AND ANALYTICS UTILITIES
# =====================================

def calculate_inventory_turnover(product=None, period_days=365):
    """
    Calculate inventory turnover ratio.
    
    Args:
        product: Optional specific product (None for all products)
        period_days: Period for calculation
        
    Returns:
        Dict: Turnover metrics
    """
    try:
        from .models import Product, StockMovement
        
        if product:
            products = [product]
        else:
            products = Product.objects.filter(is_active=True)
        
        start_date = timezone.now() - timedelta(days=period_days)
        
        results = []
        
        for prod in products:
            # Calculate cost of goods sold (COGS)
            sales_movements = StockMovement.objects.filter(
                product=prod,
                movement_type='sale',
                created_at__gte=start_date,
                quantity__lt=0
            )
            
            cogs = abs(sales_movements.aggregate(
                total=Sum(F('quantity') * F('unit_cost'))
            )['total'] or Decimal('0.00'))
            
            # Calculate average inventory value
            avg_inventory_value = prod.current_stock * prod.cost_price
            
            # Calculate turnover ratio
            turnover_ratio = float(cogs / avg_inventory_value) if avg_inventory_value > 0 else 0
            
            # Calculate days in inventory
            days_in_inventory = 365 / turnover_ratio if turnover_ratio > 0 else 365
            
            results.append({
                'product': prod,
                'cogs': cogs,
                'avg_inventory_value': avg_inventory_value,
                'turnover_ratio': turnover_ratio,
                'days_in_inventory': days_in_inventory,
                'performance': _classify_turnover_performance(turnover_ratio)
            })
        
        if product:
            return results[0] if results else {}
        else:
            return {
                'period_days': period_days,
                'total_products': len(results),
                'products': results,
                'overall_turnover': sum(r['turnover_ratio'] for r in results) / len(results) if results else 0
            }
        
    except Exception as e:
        logger.error(f"Error calculating inventory turnover: {str(e)}")
        return {}

def _classify_turnover_performance(turnover_ratio):
    """Classify turnover performance."""
    if turnover_ratio >= 12:
        return 'Excellent'
    elif turnover_ratio >= 6:
        return 'Good'
    elif turnover_ratio >= 3:
        return 'Average'
    elif turnover_ratio >= 1:
        return 'Poor'
    else:
        return 'Very Poor'

# Initialize logging
logger.info("Inventory management utilities loaded successfully")
