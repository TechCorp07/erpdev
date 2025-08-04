# inventory/models.py - Comprehensive Inventory Management Models

"""
Inventory Management System Models

This module defines the complete data structure for managing products, stock,
suppliers, and all related inventory operations. It's designed to integrate
seamlessly with your existing quote system and CRM while providing real-time
stock tracking and comprehensive business intelligence.

The models support:
- Multi-location inventory tracking
- Multi-currency pricing
- Supplier management with lead times
- Automated reorder points
- Stock movement audit trails
- Cost tracking and profit calculations
- Barcode integration
- Seasonal and category-based analytics
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from decimal import Decimal
import uuid
from django.db.models import Sum, Count, F, Q
import logging

logger = logging.getLogger(__name__)

class Category(models.Model):
    """
    Product category system with hierarchical support.
    
    This allows for nested categories like:
    Electronics > Audio > Speakers > Home Theater
    
    The hierarchical structure helps with:
    - Better product organization
    - Category-based reporting
    - Automated pricing rules per category
    - Inventory planning by product type
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='subcategories'
    )
    description = models.TextField(blank=True)
    
    # Business intelligence fields
    default_markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('30.00'),
        help_text="Default profit margin for products in this category"
    )
    
    # Inventory management settings
    default_reorder_level = models.PositiveIntegerField(
        default=10,
        help_text="Default minimum stock level for products in this category"
    )
    
    # Display and organization
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['display_order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def full_path(self):
        """Get the complete category path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)
    
    def get_absolute_url(self):
        return reverse('inventory:category_detail', kwargs={'slug': self.slug})
    
    def get_product_count(self):
        """Get total number of products in this category and subcategories"""
        return Product.objects.filter(
            Q(category=self) | Q(category__parent=self)
        ).count()
    
    def get_total_stock_value(self):
        """Calculate total value of stock in this category"""
        products = Product.objects.filter(
            Q(category=self) | Q(category__parent=self)
        ).aggregate(
            total_value=Sum(F('current_stock') * F('cost_price'))
        )
        return products['total_value'] or Decimal('0.00')

class Supplier(models.Model):
    """
    Supplier management with comprehensive business relationship tracking.
    
    This model captures everything needed to manage supplier relationships:
    - Contact information and terms
    - Performance metrics
    - Currency and pricing preferences
    - Lead times and reliability data
    - Integration with purchase order systems
    """
    
    SUPPLIER_TYPES = (
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Distributor'),
        ('wholesaler', 'Wholesaler'),
        ('local_retailer', 'Local Retailer'),
        ('import_agent', 'Import Agent'),
    )
    
    CURRENCY_CHOICES = (
        ('USD', 'US Dollar'),
        ('ZWG', 'Zimbabwe Gold'),
        ('ZAR', 'South African Rand'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    )
    
    # Basic information
    name = models.CharField(max_length=200)
    supplier_code = models.CharField(max_length=20, unique=True)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPES)
    
    # Contact details
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address information
    address_line_1 = models.CharField(max_length=200)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Zimbabwe')
    
    # Business terms
    payment_terms = models.CharField(
        max_length=100, 
        default='30 days',
        help_text="e.g., '30 days', 'Net 15', 'COD', etc."
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    minimum_order_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Performance metrics
    average_lead_time_days = models.PositiveIntegerField(
        default=30,
        help_text="Average delivery time in days"
    )
    reliability_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal('5.00'),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Reliability rating from 1-10"
    )
    
    # Tax and compliance
    tax_number = models.CharField(max_length=50, blank=True)
    requires_purchase_order = models.BooleanField(
        default=True,
        help_text="Whether this supplier requires formal POs"
    )
    
    # Status and activity
    is_active = models.BooleanField(default=True)
    is_preferred = models.BooleanField(
        default=False,
        help_text="Mark as preferred supplier for priority in sourcing"
    )
    
    # Notes and additional info
    notes = models.TextField(blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.supplier_code})"
    
    def get_absolute_url(self):
        return reverse('inventory:supplier_detail', kwargs={'pk': self.pk})
    
    @property
    def total_products(self):
        """Count of products from this supplier"""
        return self.products.filter(is_active=True).count()
    
    @property
    def total_purchase_value(self):
        """Total value of all purchases from this supplier"""
        # This would be calculated from purchase orders when that module is implemented
        return Decimal('0.00')  # Placeholder
    
    def get_recent_performance(self, days=30):
        """Get recent delivery performance metrics"""
        # Placeholder for purchase order integration
        return {
            'on_time_deliveries': 0,
            'total_deliveries': 0,
            'performance_percentage': 100
        }

class Location(models.Model):
    """
    Storage locations for inventory management.
    
    Supports multiple warehouse/storage locations:
    - Main warehouse
    - Shop floor display
    - Regional storage centers
    - Customer consignment locations
    """
    
    LOCATION_TYPES = (
        ('warehouse', 'Warehouse'),
        ('shop_floor', 'Shop Floor'),
        ('display', 'Display Area'),
        ('storage', 'Storage Room'),
        ('consignment', 'Customer Consignment'),
        ('repair', 'Repair Center'),
    )
    
    name = models.CharField(max_length=100)
    location_code = models.CharField(max_length=20, unique=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES)
    
    # Address details
    address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Operational settings
    is_active = models.BooleanField(default=True)
    is_sellable = models.BooleanField(
        default=True,
        help_text="Can products be sold from this location?"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default location for new stock receipts"
    )
    
    # Capacity management
    max_capacity = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Maximum number of items this location can hold"
    )
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.location_code})"
    
    @property
    def current_capacity_usage(self):
        """Calculate current capacity usage percentage"""
        if not self.max_capacity:
            return 0
        
        current_items = StockLevel.objects.filter(
            location=self
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return (current_items / self.max_capacity) * 100 if self.max_capacity > 0 else 0
    
    @property
    def total_stock_value(self):
        """Calculate total value of stock in this location"""
        stock_levels = StockLevel.objects.filter(location=self).select_related('product')
        total_value = sum(
            (level.quantity * level.product.cost_price) 
            for level in stock_levels
        )
        return Decimal(str(total_value))

class Product(models.Model):
    """
    Core product model with comprehensive business intelligence.
    
    This is the heart of the inventory system, capturing everything needed
    for effective product management:
    - Product identification and categorization
    - Pricing and cost management
    - Supplier relationships
    - Stock control parameters
    - Performance analytics
    """
    
    PRODUCT_TYPES = (
        ('physical', 'Physical Product'),
        ('digital', 'Digital Product'),
        ('service', 'Service'),
        ('bundle', 'Product Bundle'),
    )
    
    STOCK_STATUS_CHOICES = (
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
        ('pre_order', 'Pre-order'),
    )
    
    # Basic product information
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=100, blank=True, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Categorization
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT,
        related_name='products'
    )
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name='products'
    )
    
    # Product specifications
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='physical')
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    manufacturer_part_number = models.CharField(max_length=100, blank=True)
    
    # Physical attributes
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        null=True, 
        blank=True,
        help_text="Weight in kilograms"
    )
    dimensions = models.CharField(
        max_length=100, 
        blank=True,
        help_text="L x W x H in centimeters"
    )
    
    # Pricing information
    cost_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    selling_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Stock management
    current_stock = models.IntegerField(default=0)
    reserved_stock = models.IntegerField(
        default=0,
        help_text="Stock reserved for pending orders"
    )
    available_stock = models.IntegerField(
        default=0,
        help_text="Stock available for sale (current - reserved)"
    )
    
    # Reorder management
    reorder_level = models.PositiveIntegerField(
        default=10,
        help_text="Minimum stock level before reordering"
    )
    reorder_quantity = models.PositiveIntegerField(
        default=50,
        help_text="Quantity to order when restocking"
    )
    max_stock_level = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum stock level to maintain"
    )
    
    # Supplier information
    supplier_sku = models.CharField(max_length=100, blank=True)
    supplier_lead_time_days = models.PositiveIntegerField(default=30)
    minimum_order_quantity = models.PositiveIntegerField(default=1)
    
    # Status and flags
    is_active = models.BooleanField(default=True)
    is_serialized = models.BooleanField(
        default=False,
        help_text="Track individual serial numbers for this product"
    )
    is_perishable = models.BooleanField(
        default=False,
        help_text="Product has expiration date"
    )
    requires_quality_check = models.BooleanField(
        default=False,
        help_text="Requires quality inspection before sale"
    )
    
    # Business intelligence fields
    total_sold = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity sold to date"
    )
    total_revenue = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total revenue generated from this product"
    )
    last_sold_date = models.DateTimeField(null=True, blank=True)
    last_restocked_date = models.DateTimeField(null=True, blank=True)
    
    # SEO and display
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    is_quotable = models.BooleanField(
        default=True,
        help_text="Can this product be included in quotes?"
    )
    quote_description = models.TextField(
        blank=True,
        help_text="Description to use in quotes (if different from main description)"
    )
    minimum_quote_quantity = models.IntegerField(
        default=1,
        help_text="Minimum quantity for quotes"
    )
    bulk_discount_threshold = models.IntegerField(
        default=10,
        help_text="Quantity threshold for bulk pricing"
    )
    bulk_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Discount percentage for bulk orders"
    )
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['supplier', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        """Override save to automatically calculate available stock"""
        self.available_stock = max(0, self.current_stock - self.reserved_stock)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('inventory:product_detail', kwargs={'pk': self.pk})
    
    @property
    def profit_margin_percentage(self):
        """Calculate profit margin percentage"""
        if self.cost_price > 0:
            margin = ((self.selling_price - self.cost_price) / self.cost_price) * 100
            return round(margin, 2)
        return 0
    
    @property
    def profit_amount(self):
        """Calculate profit amount per unit"""
        return self.selling_price - self.cost_price
    
    @property
    def stock_status(self):
        """Determine current stock status"""
        if not self.is_active:
            return 'discontinued'
        elif self.available_stock <= 0:
            return 'out_of_stock'
        elif self.available_stock <= self.reorder_level:
            return 'low_stock'
        else:
            return 'in_stock'
    
    @property
    def stock_value(self):
        """Calculate total value of current stock"""
        return self.current_stock * self.cost_price
    
    @property
    def needs_reorder(self):
        """Check if product needs to be reordered"""
        return self.available_stock <= self.reorder_level and self.is_active
    
    @property
    def days_of_stock_remaining(self):
        """Estimate days of stock remaining based on average sales"""
        if self.available_stock <= 0:
            return 0
        
        # Calculate average daily sales over last 30 days
        from django.utils import timezone
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        # This would integrate with sales/quote data when available
        # For now, return a placeholder calculation
        average_daily_sales = 1  # Placeholder
        
        if average_daily_sales > 0:
            return self.available_stock / average_daily_sales
        return 999  # Plenty of stock if no recent sales
    
    def reserve_stock(self, quantity):
        """Reserve stock for an order"""
        if self.available_stock >= quantity:
            self.reserved_stock += quantity
            self.save(update_fields=['reserved_stock', 'available_stock'])
            return True
        return False
    
    def release_stock_reservation(self, quantity):
        """Release previously reserved stock"""
        if self.reserved_stock >= quantity:
            self.reserved_stock -= quantity
            self.save(update_fields=['reserved_stock', 'available_stock'])
            return True
        return False
    
    def adjust_stock(self, quantity, reason="Manual adjustment", user=None):
        """Adjust stock levels and create movement record"""
        old_stock = self.current_stock
        self.current_stock = max(0, self.current_stock + quantity)
        self.save()
        
        # Create stock movement record
        StockMovement.objects.create(
            product=self,
            movement_type='adjustment',
            quantity=quantity,
            reference=reason,
            previous_stock=old_stock,
            new_stock=self.current_stock,
            notes=f"Stock adjustment: {reason}",
            created_by=user
        )
        
        logger.info(f"Stock adjusted for {self.sku}: {old_stock} -> {self.current_stock}")

class StockLevel(models.Model):
    """
    Track stock levels by location for multi-location inventory management.
    
    This model allows you to track exactly how much stock is at each location:
    - Warehouse vs shop floor
    - Different regional locations
    - Consignment locations
    - Real-time location-specific availability
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='stock_levels')
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    
    # Tracking fields
    last_counted = models.DateTimeField(null=True, blank=True)
    last_movement = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'location')
        ordering = ['product__name', 'location__name']
    
    def __str__(self):
        return f"{self.product.name} at {self.location.name}: {self.quantity}"
    
    @property
    def available_quantity(self):
        """Available quantity at this location"""
        return max(0, self.quantity - self.reserved_quantity)
    
    @property
    def stock_value(self):
        """Value of stock at this location"""
        return self.quantity * self.product.cost_price

class StockMovement(models.Model):
    """
    Complete audit trail of all stock movements.
    
    This provides full traceability of inventory changes:
    - What moved, when, where, why, and who did it
    - Integration with sales, purchases, adjustments
    - Compliance and audit support
    - Theft detection and variance analysis
    """
    
    MOVEMENT_TYPES = (
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Stock Adjustment'),
        ('transfer', 'Location Transfer'),
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('return', 'Return'),
        ('damaged', 'Damaged Stock'),
        ('expired', 'Expired Stock'),
        ('sample', 'Sample/Demo'),
    )
    
    # Core movement information
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # Can be negative for outgoing movements
    
    # Location tracking
    from_location = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='movements_from'
    )
    to_location = models.ForeignKey(
        Location, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='movements_to'
    )
    
    # Stock level tracking
    previous_stock = models.IntegerField()
    new_stock = models.IntegerField()
    
    # Reference and documentation
    reference = models.CharField(
        max_length=100,
        help_text="Reference number (PO, Invoice, Transfer, etc.)"
    )
    notes = models.TextField(blank=True)
    
    # Cost tracking
    unit_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    total_cost = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Audit information
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['movement_type', '-created_at']),
            models.Index(fields=['reference']),
        ]
    
    def __str__(self):
        direction = "+" if self.quantity > 0 else ""
        return f"{self.product.sku}: {direction}{self.quantity} ({self.get_movement_type_display()})"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total cost if not provided"""
        if self.unit_cost and not self.total_cost:
            self.total_cost = abs(self.quantity) * self.unit_cost
        super().save(*args, **kwargs)

class StockTake(models.Model):
    """
    Physical stock counting and reconciliation.
    
    Manages the process of physically counting inventory and reconciling
    with system records:
    - Scheduled or ad-hoc stock takes
    - Location-specific or full inventory counts
    - Variance identification and resolution
    - Automatic stock adjustments
    """
    
    STATUS_CHOICES = (
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    # Stock take details
    reference = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200)
    location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE,
        null=True, 
        blank=True,
        help_text="Leave blank for full inventory count"
    )
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    scheduled_date = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results summary
    items_counted = models.PositiveIntegerField(default=0)
    variances_found = models.PositiveIntegerField(default=0)
    total_adjustment_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Notes and approval
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_stock_takes'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Stock Take {self.reference} - {self.get_status_display()}"

class StockTakeItem(models.Model):
    """
    Individual items counted during a stock take.
    
    Records the physical count vs system count for each product:
    - Expected quantity from system
    - Actual quantity found
    - Variance calculation
    - Notes about discrepancies
    """
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    
    # Count data
    system_quantity = models.IntegerField()
    counted_quantity = models.IntegerField()
    variance = models.IntegerField()  # counted - system
    
    # Cost impact
    variance_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Details
    notes = models.TextField(blank=True)
    counted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    counted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('stock_take', 'product', 'location')
    
    def save(self, *args, **kwargs):
        """Auto-calculate variance and value"""
        self.variance = self.counted_quantity - self.system_quantity
        self.variance_value = self.variance * self.product.cost_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.sku}: {self.variance:+d} variance"

class PurchaseOrder(models.Model):
    """
    Purchase orders to suppliers for inventory replenishment.
    
    Manages the complete purchase workflow:
    - Automatic generation from reorder points
    - Manual purchase orders
    - Supplier communication
    - Delivery tracking
    - Cost management
    """
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent to Supplier'),
        ('acknowledged', 'Acknowledged by Supplier'),
        ('partially_received', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    )
    
    # PO identification
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    
    # Status and dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Financial details
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='USD')
    
    # Delivery details
    delivery_location = models.ForeignKey(Location, on_delete=models.PROTECT)
    delivery_instructions = models.TextField(blank=True)
    
    # Terms and conditions
    payment_terms = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.name}"
    
    def get_absolute_url(self):
        return reverse('inventory:purchase_order_detail', kwargs={'pk': self.pk})
    
    @property
    def is_overdue(self):
        """Check if delivery is overdue"""
        if self.status in ['received', 'cancelled']:
            return False
        return timezone.now().date() > self.expected_delivery_date
    
    def calculate_totals(self):
        """Recalculate PO totals from line items"""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        # Tax calculation would go here based on supplier country/tax rules
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
        self.save(update_fields=['subtotal', 'total_amount'])

class PurchaseOrderItem(models.Model):
    """
    Individual line items on purchase orders.
    
    Tracks each product being ordered:
    - Product and quantity
    - Pricing and delivery details
    - Receiving status
    - Quality control notes
    """
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    # Order details
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Delivery tracking
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Quality and notes
    quality_check_passed = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('purchase_order', 'product')
    
    def save(self, *args, **kwargs):
        """Auto-calculate total price"""
        self.total_price = self.quantity_ordered * self.unit_price
        super().save(*args, **kwargs)
    
    @property
    def quantity_outstanding(self):
        """Quantity still to be delivered"""
        return self.quantity_ordered - self.quantity_received
    
    @property
    def is_fully_received(self):
        """Check if item is fully delivered"""
        return self.quantity_received >= self.quantity_ordered
    
    def receive_stock(self, quantity, user=None, notes=""):
        """Process receipt of stock for this PO item"""
        if quantity > self.quantity_outstanding:
            raise ValueError("Cannot receive more than outstanding quantity")
        
        # Update received quantity
        self.quantity_received += quantity
        self.save()
        
        # Update product stock
        old_stock = self.product.current_stock
        self.product.current_stock += quantity
        self.product.last_restocked_date = timezone.now()
        self.product.save()
        
        # Create stock movement
        StockMovement.objects.create(
            product=self.product,
            movement_type='purchase',
            quantity=quantity,
            reference=f"PO {self.purchase_order.po_number}",
            previous_stock=old_stock,
            new_stock=self.product.current_stock,
            unit_cost=self.unit_price,
            total_cost=quantity * self.unit_price,
            notes=f"Received from {self.purchase_order.supplier.name}. {notes}",
            created_by=user
        )
        
        logger.info(f"Received {quantity} units of {self.product.sku} from PO {self.purchase_order.po_number}")

class ReorderAlert(models.Model):
    """
    Automatic alerts for products that need reordering.
    
    The system generates these alerts when products hit reorder levels:
    - Automatic detection based on stock levels
    - Alert priority based on sales velocity
    - Integration with purchase order generation
    - Supplier lead time consideration
    """
    
    PRIORITY_CHOICES = (
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('critical', 'Critical'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('ordered', 'Purchase Order Created'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reorder_alerts')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    
    # Alert details
    current_stock = models.IntegerField()
    reorder_level = models.IntegerField()
    suggested_order_quantity = models.IntegerField()
    estimated_stockout_date = models.DateField(null=True, blank=True)
    
    # Supplier information
    suggested_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Workflow
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"Reorder Alert: {self.product.sku} ({self.get_priority_display()})"
    
    def acknowledge(self, user):
        """Acknowledge the alert"""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
    
    def resolve(self, user, purchase_order=None):
        """Mark alert as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        if purchase_order:
            self.purchase_order = purchase_order
            self.status = 'ordered'
        self.save()

# Signal handlers to maintain data integrity and automation
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

@receiver(post_save, sender=Product)
def update_stock_levels_on_product_save(sender, instance, **kwargs):
    """Ensure stock levels exist for all active locations"""
    if instance.is_active:
        for location in Location.objects.filter(is_active=True):
            StockLevel.objects.get_or_create(
                product=instance,
                location=location,
                defaults={'quantity': 0}
            )

@receiver(post_save, sender=StockMovement)
def update_product_stock_on_movement(sender, instance, created, **kwargs):
    """Update product stock when movements are created"""
    if created:
        # Update location-specific stock if locations are specified
        if instance.from_location:
            stock_level, _ = StockLevel.objects.get_or_create(
                product=instance.product,
                location=instance.from_location,
                defaults={'quantity': 0}
            )
            stock_level.quantity = max(0, stock_level.quantity - abs(instance.quantity))
            stock_level.save()
        
        if instance.to_location:
            stock_level, _ = StockLevel.objects.get_or_create(
                product=instance.product,
                location=instance.to_location,
                defaults={'quantity': 0}
            )
            stock_level.quantity += abs(instance.quantity)
            stock_level.save()

@receiver(post_save, sender=Product)
def check_reorder_level(sender, instance, **kwargs):
    """Check if product needs reordering and create alert if necessary"""
    if instance.needs_reorder and instance.is_active:
        # Check if there's already an active alert
        existing_alert = ReorderAlert.objects.filter(
            product=instance,
            status__in=['active', 'acknowledged']
        ).first()
        
        if not existing_alert:
            # Determine priority based on stock situation
            stock_ratio = instance.available_stock / max(instance.reorder_level, 1)
            if stock_ratio <= 0:
                priority = 'critical'
            elif stock_ratio <= 0.5:
                priority = 'high'
            elif stock_ratio <= 0.8:
                priority = 'medium'
            else:
                priority = 'low'
            
            ReorderAlert.objects.create(
                product=instance,
                priority=priority,
                current_stock=instance.current_stock,
                reorder_level=instance.reorder_level,
                suggested_order_quantity=instance.reorder_quantity,
                suggested_supplier=instance.supplier,
                estimated_cost=instance.reorder_quantity * instance.cost_price
            )
            
            logger.info(f"Reorder alert created for {instance.sku} - {priority} priority")

