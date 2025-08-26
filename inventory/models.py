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

class Currency(models.Model):
    """
    Multi-currency support for international suppliers
    Admin configurable with real-time or manual exchange rates
    """
    code = models.CharField(max_length=3, unique=True, help_text="ISO currency code (USD, EUR, CNY)")
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    
    # Exchange rate to base currency (USD)
    exchange_rate_to_usd = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('1.000000'),
        help_text="Exchange rate to USD (1 unit of this currency = X USD)"
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    # Auto-update settings
    auto_update_enabled = models.BooleanField(
        default=False,
        help_text="Enable automatic exchange rate updates"
    )
    api_source = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('manual', 'Manual Entry'),
            ('ecb', 'European Central Bank'),
            ('fed', 'Federal Reserve'),
            ('xe', 'XE.com'),
        ],
        default='manual'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = "Currencies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def rate_age_hours(self):
        """Get how old the exchange rate is in hours"""
        return (timezone.now() - self.last_updated).total_seconds() / 3600

class OverheadFactor(models.Model):
    """
    Dynamic overhead factors for cost calculation
    Configurable from admin - rent, electricity, storage, taxes, etc.
    """
    CALCULATION_TYPES = [
        ('fixed_per_item', 'Fixed Amount Per Item'),
        ('percentage_of_cost', 'Percentage of Product Cost'),
        ('percentage_of_order', 'Percentage of Order Value'),
        ('fixed_per_order', 'Fixed Amount Per Order'),
        ('percentage_of_weight', 'Percentage Based on Weight'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES)
    
    # Value fields - only one will be used based on calculation_type
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="Fixed amount (per item or per order)"
    )
    percentage_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Percentage rate (0-100)"
    )
    
    # Application settings
    applies_to_categories = models.ManyToManyField(
        'Category',
        blank=True,
        help_text="Leave empty to apply to all categories"
    )
    applies_to_suppliers = models.ManyToManyField(
        'Supplier',
        blank=True,
        help_text="Leave empty to apply to all suppliers"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def calculate_cost(self, product_cost, order_value, weight_kg=None):
        """Calculate the overhead cost based on the factor type"""
        if not self.is_active:
            return Decimal('0.00')
        
        if self.calculation_type == 'fixed_per_item':
            return self.fixed_amount
        elif self.calculation_type == 'percentage_of_cost':
            return product_cost * (self.percentage_rate / 100)
        elif self.calculation_type == 'percentage_of_order':
            return order_value * (self.percentage_rate / 100)
        elif self.calculation_type == 'fixed_per_order':
            return self.fixed_amount
        elif self.calculation_type == 'percentage_of_weight' and weight_kg:
            return weight_kg * (self.percentage_rate / 100)
        
        return Decimal('0.00')

class ProductAttributeDefinition(models.Model):
    """
    Dynamic attribute definitions for component families
    Admin configurable - allows adding/removing attributes per component type
    """
    FIELD_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('choice', 'Choice List'),
        ('boolean', 'Yes/No'),
        ('url', 'URL'),
        ('email', 'Email'),
    ]
    
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPES)
    component_families = models.ManyToManyField(
        'ComponentFamily',
        related_name='attribute_definitions',
        help_text="Component families that use this attribute"
    )
    
    # Field configuration
    is_required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=200, blank=True)
    help_text = models.CharField(max_length=200, blank=True)
    
    # For choice fields
    choice_options = models.JSONField(
        default=list,
        blank=True,
        help_text="For choice fields: ['Option1', 'Option2', 'Option3']"
    )
    
    # Validation rules
    min_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    validation_pattern = models.CharField(
        max_length=200,
        blank=True,
        help_text="Regex pattern for validation"
    )
    
    # Display settings
    display_order = models.PositiveIntegerField(default=0)
    show_in_listings = models.BooleanField(default=False, help_text="Show in product listings")
    show_in_search = models.BooleanField(default=False, help_text="Include in search")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['name', 'field_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_field_type_display()})"

class ComponentFamily(models.Model):
    """
    Electronics Component Families with dynamic attributes
    Examples: Resistors, Capacitors, MOSFETs, Development Boards, LEDs, etc.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    
    # Default specifications template
    default_attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Default attribute values for new products in this family"
    )
    
    # Business intelligence
    typical_markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('40.00'),
        help_text="Typical markup for this component family"
    )
    
    # Default storage bin prefix
    default_bin_prefix = models.CharField(
        max_length=10,
        blank=True,
        help_text="Default storage bin prefix (e.g., 'RES' for resistors)"
    )
    
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = "Component Families"
    
    def __str__(self):
        return self.name
    
    @property
    def required_attributes(self):
        """Get required attributes for this component family"""
        return self.attribute_definitions.filter(is_required=True)
    
    @property
    def all_attributes(self):
        """Get all attributes for this component family"""
        return self.attribute_definitions.filter(is_active=True).order_by('display_order')

class SupplierCountry(models.Model):
    """Enhanced supplier countries with detailed import information"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)
    region = models.CharField(max_length=50)
    
    # Logistics information
    average_lead_time_days = models.PositiveIntegerField(default=30)
    typical_shipping_cost_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Typical shipping cost as % of order value"
    )
    
    # Import requirements
    requires_import_permit = models.BooleanField(default=False)
    average_customs_duty_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Average customs duty percentage"
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text="VAT percentage in Zimbabwe"
    )
    
    # Documentation requirements
    requires_coc = models.BooleanField(
        default=False,
        help_text="Requires Certificate of Conformity"
    )
    requires_sabs = models.BooleanField(
        default=False,
        help_text="Requires SABS certification"
    )
    
    # Preferred shipping methods for this country
    preferred_shipping_methods = models.JSONField(
        default=list,
        help_text="Preferred shipping methods: ['air', 'sea', 'express']"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['region', 'name']
        verbose_name_plural = "Supplier Countries"
    
    def __str__(self):
        return f"{self.name} ({self.region})"

class StorageLocation(models.Model):
    """
    Physical storage locations with bin management
    Supports current single location and future multi-location expansion
    """
    LOCATION_TYPES = [
        ('warehouse', 'Warehouse'),
        ('store', 'Physical Store'),
        ('combined', 'Warehouse + Store'),
        ('supplier', 'Supplier Location'),
        ('transit', 'In Transit'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES)
    
    # Address information
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Zimbabwe')
    
    # Contact information
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Capacity and settings
    max_capacity_cubic_meters = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum storage capacity in cubic meters"
    )
    
    # Operational settings
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="Default location for new stock")
    allows_sales = models.BooleanField(default=True, help_text="Can sell from this location")
    allows_receiving = models.BooleanField(default=True, help_text="Can receive stock at this location")
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_location_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default location
        if self.is_default:
            StorageLocation.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class StorageBin(models.Model):
    """
    Storage bins within locations for organized component storage
    Each component family can have dedicated bins
    """
    location = models.ForeignKey(
        StorageLocation,
        on_delete=models.CASCADE,
        related_name='storage_bins'
    )
    bin_code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    
    # Organization
    component_families = models.ManyToManyField(
        ComponentFamily,
        blank=True,
        help_text="Component families typically stored in this bin"
    )
    
    # Physical attributes
    row = models.CharField(max_length=10, blank=True)
    column = models.CharField(max_length=10, blank=True)
    shelf = models.CharField(max_length=10, blank=True)
    
    # Capacity
    max_capacity_items = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of items this bin can hold"
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    requires_special_handling = models.BooleanField(
        default=False,
        help_text="Requires special handling (ESD, temperature control, etc.)"
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['location', 'bin_code']
        unique_together = ['location', 'bin_code']
    
    def __str__(self):
        return f"{self.location.code}-{self.bin_code}: {self.name}"
    
    @property
    def current_item_count(self):
        """Get current number of items in this bin"""
        return self.stock_levels.aggregate(
            total=Sum('quantity_on_hand')
        )['total'] or 0
    
    @property
    def utilization_percentage(self):
        """Calculate bin utilization percentage"""
        if not self.max_capacity_items:
            return None
        current = self.current_item_count
        return (current / self.max_capacity_items) * 100 if self.max_capacity_items > 0 else 0

class Brand(models.Model):
    """Enhanced brand management with quality tracking"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    
    # Business intelligence
    default_markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('30.00'),
        help_text="Default markup for this brand"
    )
    
    # Quality and reliability tracking
    quality_rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Quality rating (1-5 stars)"
    )
    warranty_period_months = models.PositiveIntegerField(
        default=12,
        help_text="Standard warranty period in months"
    )
    
    # Market positioning
    market_position = models.CharField(
        max_length=20,
        choices=[
            ('budget', 'Budget/Generic'),
            ('mid_range', 'Mid Range'),
            ('premium', 'Premium'),
            ('professional', 'Professional Grade'),
        ],
        default='mid_range'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Brands"
    
    def __str__(self):
        return self.name
    
    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()
    
    @property
    def average_markup(self):
        """Calculate average markup for this brand's products"""
        return self.products.filter(is_active=True).aggregate(
            avg_markup=models.Avg('markup_percentage')
        )['avg_markup'] or Decimal('0.00')

class Supplier(models.Model):
    """
    Supplier management with comprehensive business relationship tracking.
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
    supplier_code = models.CharField(max_length=50, unique=True)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPES)
    website = models.URLField(blank=True)
    
    # Contact details
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    
    # Address information
    address_line_1 = models.CharField(max_length=200)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Geographic Information
    country = models.ForeignKey(
        SupplierCountry,
        on_delete=models.PROTECT,
        help_text="Country where supplier is located"
    )
    
    # Business Terms
    payment_terms = models.CharField(
        max_length=100,
        default="30 days",
        help_text="e.g., '30 days', 'NET 30', 'COD', 'T/T in advance'"
    )
    minimum_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum order value"
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        help_text="Supplier's preferred currency"
    )
    
    # Shipping and Logistics
    typical_lead_time_days = models.PositiveIntegerField(
        default=30,
        help_text="Typical lead time from order to delivery"
    )
    shipping_methods = models.JSONField(
        default=list,
        help_text="Available shipping methods: ['air', 'sea', 'express', 'land']"
    )
    preferred_shipping_method = models.CharField(
        max_length=20,
        choices=[
            ('air', 'Air Freight'),
            ('sea', 'Sea Freight'),
            ('express', 'Express Courier'),
            ('land', 'Land Transport'),
        ],
        default='air'
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
    
    # Performance Tracking
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Supplier rating (1-5 stars)"
    )
    on_time_delivery_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00'),
        help_text="Percentage of on-time deliveries"
    )
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00'),
        help_text="Quality score percentage"
    )
    
    # Special terms and capabilities
    supports_dropshipping = models.BooleanField(default=False)
    provides_technical_support = models.BooleanField(default=False)
    has_local_representative = models.BooleanField(default=False)
    accepts_returns = models.BooleanField(default=True)
    return_policy_days = models.PositiveIntegerField(
        default=30,
        help_text="Return policy period in days"
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
    
    # Communication preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
            ('phone', 'Phone'),
            ('website', 'Website Portal'),
        ],
        default='email'
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
    def total_orders(self):
        return self.purchase_orders.count()
    
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
    
    @property
    def average_order_value(self):
        """Calculate average order value for this supplier"""
        avg = self.purchase_orders.aggregate(
            avg_value=models.Avg('total_amount')
        )['avg_value']
        return avg or Decimal('0.00')
  
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
    
    # Link to component family for electronics-specific features
    component_family = models.ForeignKey(
        ComponentFamily,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Electronics component family this category belongs to"
    )
    
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
    default_reorder_quantity = models.PositiveIntegerField(
        default=50,
        help_text="Default reorder quantity"
    )
    
    # Default storage settings
    preferred_storage_bins = models.ManyToManyField(
        StorageBin,
        blank=True,
        help_text="Preferred storage bins for this category"
    )
    
    # Electronics-specific settings
    requires_datasheet = models.BooleanField(
        default=False,
        help_text="Products in this category typically need datasheets"
    )
    requires_certification = models.BooleanField(
        default=False,
        help_text="Products require certification (CE, FCC, SABS, etc.)"
    )
    requires_esd_protection = models.BooleanField(
        default=False,
        help_text="Products require ESD protection during handling"
    )
    
    # Display and organization
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_in_menu = models.BooleanField(default=True)
    
    # SEO fields
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
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
            Q(category=self) | Q(category__parent=self),
            is_active=True
        ).aggregate(
            total_value=Sum(F('current_stock') * F('total_cost_price'))
        )
        return products['total_value'] or Decimal('0.00')

class Product(models.Model):
    """
    Complete Product model for electronics components
    with dynamic attributes and advanced cost calculation
    """
    
    PRODUCT_TYPES = (
        ('component', 'Electronic Component'),
        ('module', 'Electronic Module'),
        ('board', 'Development Board'),
        ('kit', 'Kit/Bundle'),
        ('tool', 'Tool/Equipment'),
        ('cable', 'Cable/Connector'),
        ('consumable', 'Consumable'),
        ('other', 'Other'),
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
    qr_code = models.CharField(max_length=200, blank=True)
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
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name='products',
        help_text="Product brand"
    )
    component_family = models.ForeignKey(
        ComponentFamily,
        on_delete=models.PROTECT,
        related_name='products',
        null=True,
        blank=True,
        help_text="Component family (auto-filled from category)"
    )
    
    # Product specifications - electronics specific
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='component')
    model_number = models.CharField(max_length=100, blank=True)
    manufacturer_part_number = models.CharField(max_length=100, blank=True)
    supplier_sku = models.CharField(max_length=100, blank=True)
    
    # Dynamic attributes (configurable per component family)
    dynamic_attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic component specifications (voltage, current, tolerance, etc.)"
    )
    
    # External resources
    datasheet_url = models.URLField(blank=True, help_text="Link to datasheet (Google Drive/Mega)")
    product_images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs for shopping cart"
    )
    additional_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional documents: certifications, test reports, etc."
    )
    
    # Physical attributes
    package_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Component package (DIP, SMD, TO-220, etc.)"
    )
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    dimensions = models.CharField(
        max_length=100,
        blank=True,
        help_text="L x W x H in mm"
    )
    volume_cubic_cm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Volume for storage optimization"
    )
    
    # Pricing information
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Cost price in supplier currency"
    )
    supplier_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='products_cost',
        help_text="Currency of cost price"
    )
    selling_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    
    # Import costs (per unit)
    shipping_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Shipping cost per unit in USD"
    )
    insurance_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Insurance cost per unit in USD"
    )
    customs_duty_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Customs duty percentage"
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text="VAT percentage"
    )
    other_fees_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Other fees (clearance, handling, etc.) per unit in USD"
    )
    
    # Calculated costs (auto-calculated)
    cost_price_usd = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Cost price converted to USD"
    )
    total_import_cost_usd = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Total import cost per unit in USD"
    )
    overhead_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Allocated overhead cost per unit"
    )
    total_cost_price_usd = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Total cost including all expenses in USD"
    )
    
    # Selling prices
    selling_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='products_selling',
        help_text="Currency for selling price"
    )
    selling_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Selling price in selling currency"
    )
    markup_percentage = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Calculated markup percentage"
    )
    
    # Competitive pricing
    competitor_min_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum competitor price found"
    )
    competitor_max_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum competitor price found"
    )
    price_position = models.CharField(
        max_length=20,
        choices=[
            ('below_market', 'Below Market'),
            ('competitive', 'Competitive'),
            ('premium', 'Premium'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    
    # Stock information with multi-location support
    total_stock = models.IntegerField(default=0, help_text="Total stock across all locations")
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
    economic_order_quantity = models.IntegerField(
        default=50,
        help_text="Calculated EOQ for optimal ordering"
    )
    
    # Supplier information
    supplier_sku = models.CharField(max_length=100, blank=True)
    supplier_lead_time_days = models.IntegerField(
        default=30,
        help_text="Lead time for this specific product"
    )
    supplier_minimum_order_quantity = models.IntegerField(
        default=1,
        help_text="MOQ from supplier"
    )
    supplier_price_breaks = models.JSONField(
        default=list,
        blank=True,
        help_text="Price breaks: [{'quantity': 100, 'price': 1.50}, {'quantity': 500, 'price': 1.25}]"
    )
    
    # Quality and compliance
    quality_grade = models.CharField(
        max_length=20,
        choices=[
            ('consumer', 'Consumer Grade'),
            ('industrial', 'Industrial Grade'),
            ('automotive', 'Automotive Grade'),
            ('military', 'Military Grade'),
            ('space', 'Space Grade'),
        ],
        default='consumer'
    )
    certifications = models.JSONField(
        default=list,
        blank=True,
        help_text="Certifications: ['CE', 'FCC', 'SABS', 'RoHS']"
    )
    
    # Status and flags
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_hazardous = models.BooleanField(
        default=False,
        help_text="Requires special handling/shipping"
    )
    requires_esd_protection = models.BooleanField(
        default=False,
        help_text="Requires ESD protection"
    )
    is_temperature_sensitive = models.BooleanField(
        default=False,
        help_text="Requires temperature-controlled storage"
    )
    is_serialized = models.BooleanField(
        default=False,
        help_text="Track individual serial numbers for this product"
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
        max_digits=20, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total revenue generated from this product"
    )
    last_sold_date = models.DateTimeField(null=True, blank=True)
    last_restocked_date = models.DateTimeField(null=True, blank=True)
    last_cost_update = models.DateTimeField(auto_now=True)
    
    # SEO and display
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    search_keywords = models.TextField(blank=True, help_text="Comma-separated keywords")
    
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
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['qr_code']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['supplier', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['component_family', 'is_active']),
            models.Index(fields=['total_stock']),
            models.Index(fields=['reorder_level']),
            models.Index(fields=['manufacturer_part_number']),
            models.Index(fields=['supplier_sku']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        """Enhanced save method with cost calculations"""
        self.calculate_all_costs()
        
        # Auto-set component family from category
        if self.category and self.category.component_family:
            self.component_family = self.category.component_family
        
        # Generate QR code if not exists
        if not self.qr_code:
            self.qr_code = f"BT-{self.sku}-{timezone.now().strftime('%Y%m%d')}"
        
        super().save(*args, **kwargs)
    
    def calculate_all_costs(self):
        """Calculate all cost components"""
        # Convert cost price to USD
        if self.supplier_currency:
            self.cost_price_usd = self.cost_price * self.supplier_currency.exchange_rate_to_usd
        else:
            self.cost_price_usd = self.cost_price
        
        # Calculate import costs
        customs_duty = self.cost_price_usd * (self.customs_duty_percentage / 100)
        vat_on_cost = (self.cost_price_usd + customs_duty) * (self.vat_percentage / 100)
        
        self.total_import_cost_usd = (
            self.cost_price_usd +
            self.shipping_cost_per_unit +
            self.insurance_cost_per_unit +
            customs_duty +
            vat_on_cost +
            self.other_fees_per_unit
        )
        
        # Calculate overhead costs
        self.calculate_overhead_costs()
        
        # Calculate total cost
        self.total_cost_price_usd = self.total_import_cost_usd + self.overhead_cost_per_unit
        
        # Calculate markup percentage
        if self.total_cost_price_usd and self.selling_price and self.selling_currency:
            selling_price_usd = self.selling_price
            if self.selling_currency.code != 'USD':
                selling_price_usd = self.selling_price * self.selling_currency.exchange_rate_to_usd
            
            if self.total_cost_price_usd > 0:
                markup = ((selling_price_usd - self.total_cost_price_usd) / self.total_cost_price_usd) * 100
                self.markup_percentage = markup
    
    def calculate_overhead_costs(self):
        """Calculate allocated overhead costs per unit"""
        overhead_total = Decimal('0.00')
        
        # Get all active overhead factors
        overhead_factors = OverheadFactor.objects.filter(is_active=True)
        
        for factor in overhead_factors:
            # Check if factor applies to this product
            applies = True
            
            if factor.applies_to_categories.exists():
                applies = applies and factor.applies_to_categories.filter(id=self.category.id).exists()
            
            if factor.applies_to_suppliers.exists():
                applies = applies and factor.applies_to_suppliers.filter(id=self.supplier.id).exists()
            
            if applies:
                cost = factor.calculate_cost(
                    product_cost=self.total_import_cost_usd,
                    order_value=self.total_import_cost_usd,  # For single item
                    weight_kg=self.weight_grams / 1000 if self.weight_grams else None
                )
                overhead_total += cost
        
        self.overhead_cost_per_unit = overhead_total
    
    def get_absolute_url(self):
        return reverse('inventory:product_detail', kwargs={'pk': self.pk})
    
    @property
    def available_stock(self):
        """Calculate available stock (total - reserved)"""
        return max(0, self.total_stock - self.reserved_stock)
    
    @property
    def profit_margin_percentage(self):
        """Calculate profit margin percentage"""
        if self.cost_price > 0:
            margin = ((self.selling_price - self.cost_price) / self.cost_price) * 100
            return round(margin, 2)
        return 0
    
    @property
    def profit_per_unit_usd(self):
        """Calculate profit per unit in USD"""
        if self.selling_currency and self.selling_price:
            selling_price_usd = self.selling_price
            if self.selling_currency.code != 'USD':
                selling_price_usd = self.selling_price * self.selling_currency.exchange_rate_to_usd
            return selling_price_usd - self.total_cost_price_usd
        return Decimal('0.00')
    
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
    def stock_value_usd(self):
        """Calculate total stock value in USD"""
        return self.total_stock * self.total_cost_price_usd
    
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
    
    def get_attribute_value(self, attribute_name):
        """Get value of a dynamic attribute"""
        return self.dynamic_attributes.get(attribute_name, '')
    
    def set_attribute_value(self, attribute_name, value):
        """Set value of a dynamic attribute"""
        if not self.dynamic_attributes:
            self.dynamic_attributes = {}
        self.dynamic_attributes[attribute_name] = value
    
    def get_stock_at_location(self, location):
        """Get stock level at specific location"""
        try:
            stock_level = self.stock_levels.get(location=location)
            return stock_level.quantity_on_hand
        except:
            return 0
    
    def get_preferred_supplier_price(self, quantity=1):
        """Get best price from supplier based on quantity breaks"""
        if not self.supplier_price_breaks:
            return self.cost_price
        
        best_price = self.cost_price
        for price_break in self.supplier_price_breaks:
            if quantity >= price_break.get('quantity', 0):
                best_price = Decimal(str(price_break.get('price', self.cost_price)))
        
        return best_price

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

class ProductStockLevel(models.Model):
    """Stock levels per product per location with bin tracking"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels')
    location = models.ForeignKey(StorageLocation, on_delete=models.CASCADE)
    storage_bin = models.ForeignKey(StorageBin, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantity_on_hand = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(default=0)
    quantity_on_order = models.IntegerField(default=0)
    
    # Last movements
    last_movement_date = models.DateTimeField(null=True, blank=True)
    last_count_date = models.DateTimeField(null=True, blank=True)
    last_count_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['product', 'location']
        ordering = ['product', 'location']
    
    def __str__(self):
        return f"{self.product.sku} @ {self.location.code}: {self.quantity_on_hand}"
    
    @property
    def available_quantity(self):
        """Calculate available quantity"""
        return max(0, self.quantity_on_hand - self.quantity_reserved)
    
    def save(self, *args, **kwargs):
        """Update product total stock when stock level changes"""
        super().save(*args, **kwargs)
        
        # Update product total stock
        total = ProductStockLevel.objects.filter(
            product=self.product,
            is_active=True
        ).aggregate(
            total_stock=Sum('quantity_on_hand'),
            total_reserved=Sum('quantity_reserved')
        )
        
        self.product.total_stock = total['total_stock'] or 0
        self.product.reserved_stock = total['total_reserved'] or 0
        self.product.save(update_fields=['total_stock', 'reserved_stock'])

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

