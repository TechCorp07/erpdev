# inventory/signals.py - Automated Inventory Management Signals

"""
Django Signals for Inventory Management Automation

This module provides intelligent automation for inventory operations through
Django's signal system. It handles automatic stock updates, reorder alerts,
notification generation, and business rule enforcement.

Key Automation Features:
- Automatic stock level synchronization
- Real-time reorder alert generation
- Stock movement audit trail creation
- Purchase order workflow automation
- Integration with core notification system
- Performance metric tracking
- Business rule validation

The signals work seamlessly with your existing core system while adding
sophisticated inventory management automation that reduces manual work
and prevents common inventory management errors.
"""

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from .models import (
    Product, StockLevel, StockMovement, PurchaseOrder, PurchaseOrderItem,
    ReorderAlert, StockTake, StockTakeItem, Category, Supplier, Location
)
from inventory import models

logger = logging.getLogger(__name__)

# =====================================
# PRODUCT LIFECYCLE SIGNALS
# =====================================

@receiver(post_save, sender=Product)
def handle_product_creation_and_updates(sender, instance, created, **kwargs):
    """
    Handle product creation and updates with automatic setup.
    
    When a product is created or updated, this signal:
    - Creates stock levels for all active locations
    - Updates stock availability calculations
    - Checks reorder level requirements
    - Generates notifications for significant changes
    - Integrates with quote system for pricing updates
    """
    try:
        with transaction.atomic():
            if created:
                # New product - set up stock levels for all active locations
                logger.info(f"Setting up new product: {instance.sku}")
                
                active_locations = Location.objects.filter(is_active=True)
                for location in active_locations:
                    StockLevel.objects.get_or_create(
                        product=instance,
                        location=location,
                        defaults={
                            'quantity': 0,
                            'reserved_quantity': 0
                        }
                    )
                
                # Create notification for product creation
                from core.utils import create_notification
                
                # Notify inventory managers about new product
                from django.contrib.auth.models import User
                inventory_managers = User.objects.filter(
                    profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
                    profile__is_active=True
                ).exclude(id=instance.created_by.id if instance.created_by else None)
                
                for manager in inventory_managers:
                    create_notification(
                        user=manager,
                        title="New Product Added",
                        message=f"Product '{instance.name}' ({instance.sku}) has been added to inventory by {instance.created_by.get_full_name() if instance.created_by else 'System'}",
                        notification_type="info",
                        action_url=f"/inventory/products/{instance.id}/",
                        action_text="View Product"
                    )
                
                logger.info(f"Product {instance.sku} set up successfully with stock levels")
            
            else:
                # Existing product - check for significant changes
                _handle_product_updates(instance)
                
    except Exception as e:
        logger.error(f"Error in product signal handler: {str(e)}")

def _handle_product_updates(product):
    """Handle updates to existing products"""
    try:
        # Get the previous version from database to compare changes
        try:
            old_product = Product.objects.get(pk=product.pk)
        except Product.DoesNotExist:
            return
        
        # Check for significant price changes (>10%)
        if old_product.selling_price != product.selling_price:
            price_change_percent = abs(
                (product.selling_price - old_product.selling_price) / old_product.selling_price * 100
            ) if old_product.selling_price > 0 else 0
            
            if price_change_percent > 10:
                _notify_price_change(product, old_product.selling_price, product.selling_price)
        
        # Check for reorder level changes
        if old_product.reorder_level != product.reorder_level:
            _update_reorder_alerts(product)
        
        # Check if product was activated/deactivated
        if old_product.is_active != product.is_active:
            _handle_product_status_change(product)
        
        logger.debug(f"Product {product.sku} updates processed")
        
    except Exception as e:
        logger.error(f"Error handling product updates for {product.sku}: {str(e)}")

def _notify_price_change(product, old_price, new_price):
    """Notify relevant users about significant price changes"""
    try:
        from core.utils import create_bulk_notifications
        from django.contrib.auth.models import User
        
        # Notify sales team and managers
        users_to_notify = User.objects.filter(
            profile__user_type__in=['sales_rep', 'sales_manager', 'blitzhub_admin'],
            profile__is_active=True
        )
        
        change_percent = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0
        direction = "increased" if new_price > old_price else "decreased"
        
        create_bulk_notifications(
            users=users_to_notify,
            title=f"Price Change: {product.name}",
            message=f"Product {product.sku} price {direction} by {abs(change_percent):.1f}% (${old_price:.2f} → ${new_price:.2f})",
            notification_type="info",
            action_url=f"/inventory/products/{product.id}/",
            action_text="View Product"
        )
        
        logger.info(f"Price change notification sent for {product.sku}")
        
    except Exception as e:
        logger.error(f"Error sending price change notification: {str(e)}")

def _update_reorder_alerts(product):
    """Update reorder alerts when reorder level changes"""
    try:
        # Cancel existing alerts if reorder level increased above current stock
        if product.current_stock > product.reorder_level:
            ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).update(status='resolved', resolved_at=timezone.now())
            
            logger.info(f"Resolved reorder alerts for {product.sku} - stock above new reorder level")
        
        # Create new alert if stock is below new reorder level
        elif product.current_stock <= product.reorder_level and product.is_active:
            existing_alert = ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).first()
            
            if not existing_alert:
                _create_reorder_alert(product)
        
    except Exception as e:
        logger.error(f"Error updating reorder alerts for {product.sku}: {str(e)}")

def _handle_product_status_change(product):
    """Handle product activation/deactivation"""
    try:
        if not product.is_active:
            # Product deactivated - resolve any active reorder alerts
            ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).update(status='resolved', resolved_at=timezone.now())
            
            logger.info(f"Resolved reorder alerts for deactivated product {product.sku}")
        
    except Exception as e:
        logger.error(f"Error handling status change for {product.sku}: {str(e)}")

# =====================================
# STOCK MOVEMENT AUTOMATION
# =====================================

@receiver(post_save, sender=StockMovement)
def handle_stock_movement_effects(sender, instance, created, **kwargs):
    """
    Handle automatic effects of stock movements.
    
    When stock moves, this signal:
    - Updates product stock levels
    - Updates location-specific stock levels
    - Checks reorder requirements
    - Updates product performance metrics
    - Generates relevant notifications
    """
    if not created:
        return
    
    try:
        with transaction.atomic():
            product = instance.product
            
            # Update location-specific stock levels
            _update_location_stock_levels(instance)
            
            # Update product total stock from all locations
            _sync_product_total_stock(product)
            
            # Check reorder requirements
            _check_reorder_requirements(product)
            
            # Update product performance metrics
            _update_product_metrics(instance)
            
            # Generate notifications for significant movements
            _notify_significant_movements(instance)
            
            logger.debug(f"Stock movement processed: {instance}")
            
    except Exception as e:
        logger.error(f"Error processing stock movement {instance.id}: {str(e)}")

def _update_location_stock_levels(movement):
    """Update stock levels at specific locations"""
    try:
        product = movement.product
        
        # Update 'from' location
        if movement.from_location:
            from_stock, created = StockLevel.objects.get_or_create(
                product=product,
                location=movement.from_location,
                defaults={'quantity': 0, 'reserved_quantity': 0}
            )
            
            if movement.quantity < 0:  # Outgoing movement
                from_stock.quantity = max(0, from_stock.quantity + movement.quantity)
                from_stock.save()
        
        # Update 'to' location
        if movement.to_location:
            to_stock, created = StockLevel.objects.get_or_create(
                product=product,
                location=movement.to_location,
                defaults={'quantity': 0, 'reserved_quantity': 0}
            )
            
            if movement.quantity > 0:  # Incoming movement
                to_stock.quantity += movement.quantity
                to_stock.save()
        
    except Exception as e:
        logger.error(f"Error updating location stock levels: {str(e)}")

def _sync_product_total_stock(product):
    """Synchronize product total stock from all locations"""
    try:
        total_stock = StockLevel.objects.filter(product=product).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        if product.current_stock != total_stock:
            product.current_stock = total_stock
            product.save(update_fields=['current_stock', 'available_stock'])
            
            logger.debug(f"Synced total stock for {product.sku}: {total_stock}")
        
    except Exception as e:
        logger.error(f"Error syncing total stock for {product.sku}: {str(e)}")

def _check_reorder_requirements(product):
    """Check if product needs reordering after stock movement"""
    try:
        if product.needs_reorder and product.is_active:
            # Check if there's already an active alert
            existing_alert = ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).first()
            
            if not existing_alert:
                _create_reorder_alert(product)
        
    except Exception as e:
        logger.error(f"Error checking reorder requirements for {product.sku}: {str(e)}")

def _create_reorder_alert(product):
    """Create a new reorder alert for a product"""
    try:
        # Determine priority based on stock situation
        if product.available_stock <= 0:
            priority = 'critical'
        elif product.available_stock <= (product.reorder_level * 0.5):
            priority = 'high'
        elif product.available_stock <= (product.reorder_level * 0.8):
            priority = 'medium'
        else:
            priority = 'low'
        
        # Calculate estimated stockout date based on average usage
        estimated_stockout_date = _calculate_stockout_date(product)
        
        alert = ReorderAlert.objects.create(
            product=product,
            priority=priority,
            current_stock=product.current_stock,
            reorder_level=product.reorder_level,
            suggested_order_quantity=product.reorder_quantity,
            suggested_supplier=product.supplier,
            estimated_cost=product.reorder_quantity * product.cost_price,
            estimated_stockout_date=estimated_stockout_date
        )
        
        # Notify relevant users
        _notify_reorder_alert(alert)
        
        logger.info(f"Created {priority} reorder alert for {product.sku}")
        
    except Exception as e:
        logger.error(f"Error creating reorder alert for {product.sku}: {str(e)}")

def _calculate_stockout_date(product):
    """Calculate estimated stockout date based on usage patterns"""
    try:
        from django.utils import timezone
        from django.db.models import Sum
        
        # Calculate average daily usage over last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        recent_outgoing_movements = StockMovement.objects.filter(
            product=product,
            movement_type__in=['out', 'sale'],
            created_at__gte=thirty_days_ago,
            quantity__lt=0
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        daily_usage = abs(recent_outgoing_movements) / 30 if recent_outgoing_movements else 1
        
        if daily_usage > 0 and product.available_stock > 0:
            days_remaining = product.available_stock / daily_usage
            return timezone.now().date() + timezone.timedelta(days=int(days_remaining))
        
        return None
        
    except Exception as e:
        logger.error(f"Error calculating stockout date for {product.sku}: {str(e)}")
        return None

def _notify_reorder_alert(alert):
    """Notify relevant users about reorder alerts"""
    try:
        from core.utils import create_bulk_notifications
        from django.contrib.auth.models import User
        
        # Notify inventory managers and purchasing team
        users_to_notify = User.objects.filter(
            profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
            profile__is_active=True
        )
        
        urgency_text = {
            'critical': '🚨 CRITICAL',
            'high': '⚠️ HIGH PRIORITY',
            'medium': '📋 MEDIUM',
            'low': '📝 LOW'
        }.get(alert.priority, alert.priority.upper())
        
        create_bulk_notifications(
            users=users_to_notify,
            title=f"Reorder Alert: {alert.product.name}",
            message=f"{urgency_text} - {alert.product.sku} is at {alert.current_stock} units (reorder level: {alert.reorder_level})",
            notification_type="warning" if alert.priority in ['high', 'critical'] else "info",
            action_url=f"/inventory/reorder-alerts/{alert.id}/",
            action_text="View Alert"
        )
        
        logger.info(f"Reorder alert notification sent for {alert.product.sku}")
        
    except Exception as e:
        logger.error(f"Error sending reorder alert notification: {str(e)}")

def _update_product_metrics(movement):
    """Update product performance metrics based on movement"""
    try:
        product = movement.product
        
        # Update sales metrics for sale movements
        if movement.movement_type == 'sale' and movement.quantity < 0:
            product.total_sold += abs(movement.quantity)
            product.last_sold_date = movement.created_at
            
            # Calculate revenue if unit cost is available
            if movement.unit_cost:
                revenue = abs(movement.quantity) * movement.unit_cost
                product.total_revenue += revenue
        
        # Update restock date for incoming stock
        elif movement.movement_type in ['purchase', 'in'] and movement.quantity > 0:
            product.last_restocked_date = movement.created_at
        
        product.save(update_fields=[
            'total_sold', 'total_revenue', 'last_sold_date', 'last_restocked_date'
        ])
        
    except Exception as e:
        logger.error(f"Error updating product metrics: {str(e)}")

def _notify_significant_movements(movement):
    """Notify about significant stock movements"""
    try:
        # Define what constitutes a "significant" movement
        if abs(movement.quantity) >= 100 or (movement.unit_cost and movement.total_cost >= 1000):
            from core.utils import create_notification
            from django.contrib.auth.models import User
            
            # Notify inventory managers
            managers = User.objects.filter(
                profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
                profile__is_active=True
            )
            
            movement_type_display = movement.get_movement_type_display()
            direction = "+" if movement.quantity > 0 else ""
            
            for manager in managers:
                create_notification(
                    user=manager,
                    title=f"Significant Stock Movement",
                    message=f"{movement_type_display}: {direction}{movement.quantity} units of {movement.product.name} ({movement.reference})",
                    notification_type="info",
                    action_url=f"/inventory/stock-movements/?product={movement.product.id}",
                    action_text="View History"
                )
        
    except Exception as e:
        logger.error(f"Error sending significant movement notification: {str(e)}")

# =====================================
# PURCHASE ORDER WORKFLOW SIGNALS
# =====================================

@receiver(post_save, sender=PurchaseOrder)
def handle_purchase_order_workflow(sender, instance, created, **kwargs):
    """
    Handle purchase order workflow automation.
    
    Manages PO status changes, notifications, and integrations.
    """
    try:
        if created:
            _handle_new_purchase_order(instance)
        else:
            _handle_purchase_order_updates(instance)
            
    except Exception as e:
        logger.error(f"Error in purchase order workflow: {str(e)}")

def _handle_new_purchase_order(po):
    """Handle new purchase order creation"""
    try:
        # Notify purchasing team
        from core.utils import create_bulk_notifications
        from django.contrib.auth.models import User
        
        purchasing_team = User.objects.filter(
            profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
            profile__is_active=True
        )
        
        create_bulk_notifications(
            users=purchasing_team,
            title="New Purchase Order Created",
            message=f"PO {po.po_number} for {po.supplier.name} has been created (${po.total_amount:.2f})",
            notification_type="info",
            action_url=f"/inventory/purchase-orders/{po.id}/",
            action_text="View PO"
        )
        
        logger.info(f"New purchase order {po.po_number} created and notifications sent")
        
    except Exception as e:
        logger.error(f"Error handling new purchase order: {str(e)}")

def _handle_purchase_order_updates(po):
    """Handle purchase order status updates"""
    try:
        # Get previous state to detect status changes
        try:
            old_po = PurchaseOrder.objects.get(pk=po.pk)
        except PurchaseOrder.DoesNotExist:
            return
        
        # Handle status changes
        if old_po.status != po.status:
            _handle_po_status_change(po, old_po.status, po.status)
        
    except Exception as e:
        logger.error(f"Error handling purchase order updates: {str(e)}")

def _handle_po_status_change(po, old_status, new_status):
    """Handle purchase order status changes"""
    try:
        from core.utils import create_notification
        
        # Notify PO creator about status changes
        if po.created_by:
            status_messages = {
                'sent': f"Purchase order {po.po_number} has been sent to {po.supplier.name}",
                'acknowledged': f"Purchase order {po.po_number} has been acknowledged by {po.supplier.name}",
                'received': f"Purchase order {po.po_number} has been fully received",
                'cancelled': f"Purchase order {po.po_number} has been cancelled"
            }
            
            message = status_messages.get(new_status, f"Purchase order {po.po_number} status changed to {new_status}")
            
            create_notification(
                user=po.created_by,
                title="Purchase Order Status Update",
                message=message,
                notification_type="success" if new_status == 'received' else "info",
                action_url=f"/inventory/purchase-orders/{po.id}/",
                action_text="View PO"
            )
        
        logger.info(f"PO {po.po_number} status changed from {old_status} to {new_status}")
        
    except Exception as e:
        logger.error(f"Error handling PO status change: {str(e)}")

@receiver(post_save, sender=PurchaseOrderItem)
def handle_purchase_order_item_updates(sender, instance, created, **kwargs):
    """
    Handle purchase order item changes and stock receipts.
    
    When PO items are updated (especially quantity received),
    this triggers stock updates and related notifications.
    """
    if not created:
        try:
            _handle_po_item_receipt(instance)
        except Exception as e:
            logger.error(f"Error handling PO item updates: {str(e)}")

def _handle_po_item_receipt(po_item):
    """Handle receipt of purchase order items"""
    try:
        # Check if this is a stock receipt (quantity_received increased)
        try:
            old_item = PurchaseOrderItem.objects.get(pk=po_item.pk)
            if old_item.quantity_received < po_item.quantity_received:
                received_qty = po_item.quantity_received - old_item.quantity_received
                _process_stock_receipt(po_item, received_qty)
        except PurchaseOrderItem.DoesNotExist:
            pass
        
    except Exception as e:
        logger.error(f"Error handling PO item receipt: {str(e)}")

def _process_stock_receipt(po_item, received_qty):
    """Process stock receipt from purchase order"""
    try:
        with transaction.atomic():
            product = po_item.product
            po = po_item.purchase_order
            
            # Create stock movement
            StockMovement.objects.create(
                product=product,
                movement_type='purchase',
                quantity=received_qty,
                reference=f"PO {po.po_number}",
                to_location=po.delivery_location,
                previous_stock=product.current_stock,
                new_stock=product.current_stock + received_qty,
                unit_cost=po_item.unit_price,
                total_cost=received_qty * po_item.unit_price,
                notes=f"Received from {po.supplier.name}",
                created_by=None  # System generated
            )
            
            # Update product stock
            product.current_stock += received_qty
            product.last_restocked_date = timezone.now()
            product.save()
            
            # Resolve reorder alerts if stock is now above reorder level
            if product.current_stock > product.reorder_level:
                ReorderAlert.objects.filter(
                    product=product,
                    status__in=['active', 'acknowledged']
                ).update(status='resolved', resolved_at=timezone.now())
            
            logger.info(f"Processed stock receipt: {received_qty} units of {product.sku} from PO {po.po_number}")
        
    except Exception as e:
        logger.error(f"Error processing stock receipt: {str(e)}")

# =====================================
# STOCK TAKE SIGNALS
# =====================================

@receiver(post_save, sender=StockTakeItem)
def handle_stock_take_variance(sender, instance, created, **kwargs):
    """
    Handle stock take variance processing.
    
    When stock take items are recorded, this signal:
    - Calculates variances automatically
    - Creates adjustment movements for approved variances
    - Generates variance reports and notifications
    """
    try:
        if created or instance.variance != 0:
            _process_stock_take_variance(instance)
            
    except Exception as e:
        logger.error(f"Error handling stock take variance: {str(e)}")

def _process_stock_take_variance(stock_take_item):
    """Process variance found during stock take"""
    try:
        # Calculate variance if not already done
        if not hasattr(stock_take_item, 'variance') or stock_take_item.variance == 0:
            variance = stock_take_item.counted_quantity - stock_take_item.system_quantity
            stock_take_item.variance = variance
            stock_take_item.variance_value = variance * stock_take_item.product.cost_price
            stock_take_item.save()
        
        # If stock take is approved and there's a variance, create adjustment
        if (stock_take_item.stock_take.status == 'completed' and 
            stock_take_item.stock_take.approved_by and 
            stock_take_item.variance != 0):
            
            _create_variance_adjustment(stock_take_item)
        
        # Notify about significant variances
        if abs(stock_take_item.variance_value) > 100:  # Significant variance threshold
            _notify_significant_variance(stock_take_item)
        
    except Exception as e:
        logger.error(f"Error processing stock take variance: {str(e)}")

def _create_variance_adjustment(stock_take_item):
    """Create stock adjustment for approved variance"""
    try:
        with transaction.atomic():
            product = stock_take_item.product
            variance = stock_take_item.variance
            
            # Create stock movement for the adjustment
            StockMovement.objects.create(
                product=product,
                movement_type='adjustment',
                quantity=variance,
                reference=f"Stock Take {stock_take_item.stock_take.reference}",
                to_location=stock_take_item.location if variance > 0 else None,
                from_location=stock_take_item.location if variance < 0 else None,
                previous_stock=product.current_stock,
                new_stock=product.current_stock + variance,
                unit_cost=product.cost_price,
                total_cost=abs(variance) * product.cost_price,
                notes=f"Stock take variance adjustment: {stock_take_item.notes or 'No notes'}",
                created_by=stock_take_item.stock_take.approved_by
            )
            
            # Update product stock
            product.current_stock += variance
            product.save()
            
            logger.info(f"Created variance adjustment: {variance} units of {product.sku}")
        
    except Exception as e:
        logger.error(f"Error creating variance adjustment: {str(e)}")

def _notify_significant_variance(stock_take_item):
    """Notify about significant variances found during stock take"""
    try:
        from core.utils import create_bulk_notifications
        from django.contrib.auth.models import User
        
        # Notify inventory managers about significant variances
        managers = User.objects.filter(
            profile__user_type__in=['sales_manager', 'blitzhub_admin', 'it_admin'],
            profile__is_active=True
        )
        
        variance_type = "shortage" if stock_take_item.variance < 0 else "overage"
        
        create_bulk_notifications(
            users=managers,
            title=f"Significant Stock Variance Found",
            message=f"Stock take {stock_take_item.stock_take.reference}: {variance_type} of {abs(stock_take_item.variance)} units of {stock_take_item.product.name} (${abs(stock_take_item.variance_value):.2f})",
            notification_type="warning",
            action_url=f"/inventory/stock-takes/{stock_take_item.stock_take.id}/",
            action_text="Review Stock Take"
        )
        
        logger.info(f"Significant variance notification sent for {stock_take_item.product.sku}")
        
    except Exception as e:
        logger.error(f"Error sending variance notification: {str(e)}")

# =====================================
# CATEGORY AND SUPPLIER SIGNALS
# =====================================

@receiver(post_save, sender=Category)
def handle_category_changes(sender, instance, created, **kwargs):
    """
    Handle category creation and updates.
    
    When categories change, update related products with new defaults.
    """
    try:
        if not created:
            # Category updated - apply changes to products if requested
            _apply_category_defaults_to_products(instance)
            
    except Exception as e:
        logger.error(f"Error handling category changes: {str(e)}")

def _apply_category_defaults_to_products(category):
    """Apply category defaults to existing products (if requested)"""
    try:
        # This could be enhanced to apply category defaults automatically
        # For now, we'll just log the change
        product_count = category.products.filter(is_active=True).count()
        
        if product_count > 0:
            logger.info(f"Category {category.name} updated - {product_count} products may need review")
        
    except Exception as e:
        logger.error(f"Error applying category defaults: {str(e)}")

@receiver(post_save, sender=Supplier)
def handle_supplier_changes(sender, instance, created, **kwargs):
    """
    Handle supplier creation and updates.
    
    When supplier information changes, update related products and POs.
    """
    try:
        if not created:
            _handle_supplier_updates(instance)
            
    except Exception as e:
        logger.error(f"Error handling supplier changes: {str(e)}")

def _handle_supplier_updates(supplier):
    """Handle updates to supplier information"""
    try:
        # Get previous state to detect significant changes
        try:
            old_supplier = Supplier.objects.get(pk=supplier.pk)
        except Supplier.DoesNotExist:
            return
        
        # Check for lead time changes
        if old_supplier.average_lead_time_days != supplier.average_lead_time_days:
            product_count = supplier.products.filter(is_active=True).count()
            
            if product_count > 0:
                logger.info(f"Supplier {supplier.name} lead time changed - {product_count} products affected")
        
        # Check for currency changes
        if old_supplier.currency != supplier.currency:
            logger.warning(f"Supplier {supplier.name} currency changed from {old_supplier.currency} to {supplier.currency}")
        
    except Exception as e:
        logger.error(f"Error handling supplier updates: {str(e)}")

# =====================================
# CLEANUP AND MAINTENANCE SIGNALS
# =====================================

@receiver(pre_delete, sender=Product)
def handle_product_deletion(sender, instance, **kwargs):
    """
    Handle product deletion with proper cleanup.
    
    Before deleting a product, ensure proper cleanup of related data.
    """
    try:
        # Check if product has any stock movements (should prevent deletion)
        if instance.stock_movements.exists():
            logger.warning(f"Attempted to delete product {instance.sku} with existing stock movements")
            # Note: In production, you might want to prevent deletion here
        
        # Cancel any active reorder alerts
        ReorderAlert.objects.filter(
            product=instance,
            status__in=['active', 'acknowledged']
        ).update(status='cancelled', resolved_at=timezone.now())
        
        logger.info(f"Product {instance.sku} deletion cleanup completed")
        
    except Exception as e:
        logger.error(f"Error in product deletion cleanup: {str(e)}")

# =====================================
# PERFORMANCE MONITORING SIGNALS
# =====================================

@receiver(post_save, sender=StockMovement)
def monitor_inventory_performance(sender, instance, created, **kwargs):
    """
    Monitor inventory performance metrics.
    
    Track key performance indicators for inventory management.
    """
    if not created:
        return
    
    try:
        # This could be expanded to track various KPIs
        # For now, we'll log significant events
        
        if instance.movement_type == 'sale' and abs(instance.quantity) > 50:
            logger.info(f"Large sale recorded: {abs(instance.quantity)} units of {instance.product.sku}")
        
        if instance.movement_type == 'purchase' and instance.total_cost and instance.total_cost > 5000:
            logger.info(f"Large purchase recorded: ${instance.total_cost:.2f} worth of {instance.product.sku}")
        
    except Exception as e:
        logger.error(f"Error in performance monitoring: {str(e)}")

# Initialize signal connections
logger.info("Inventory management signals initialized")
