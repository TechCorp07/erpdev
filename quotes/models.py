from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from decimal import Decimal
import uuid

class Quote(models.Model):
    """
    The main quote model - think of this as a sophisticated proposal document
    that knows everything about pricing, timing, and client preferences.
    """
    
    # Status choices that reflect real business workflow
    STATUS_CHOICES = [
        ('draft', 'Draft'),           # Being created, not yet sent
        ('sent', 'Sent'),             # Delivered to client
        ('viewed', 'Viewed'),         # Client has opened the quote
        ('under_review', 'Under Review'),  # Client is considering
        ('accepted', 'Accepted'),     # Client approved - ready to convert
        ('rejected', 'Rejected'),     # Client declined
        ('expired', 'Expired'),       # Past validity date
        ('converted', 'Converted'),   # Became a sale/order
        ('cancelled', 'Cancelled'),   # Cancelled before completion
    ]
    
    # Priority levels for internal management
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
    ]
    
    # Core identification
    quote_id = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True,
        help_text="Unique identifier for this quote"
    )
    quote_number = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Human-readable quote number (e.g., QUO-2024-0001)"
    )
    
    # Client relationship - this connects to your excellent CRM
    client = models.ForeignKey(
        'crm.Client',  # Direct link to your CRM
        on_delete=models.CASCADE,
        related_name='quotes',
        help_text="The client this quote is for"
    )
    
    # Quote content and presentation
    title = models.CharField(
        max_length=200,
        help_text="Brief description of what this quote covers"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description or notes about this quote"
    )
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes not visible to client"
    )
    
    # Business workflow status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Financial calculations
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Sum of all line items before tax"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),  # Zimbabwe VAT rate
        help_text="Tax rate percentage"
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated tax amount"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall discount percentage"
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated discount amount"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Final amount after tax and discount"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        choices=[('USD', 'US Dollar'), ('ZWG', 'Zimbabwe Gold')]
    )
    
    # Terms and conditions
    payment_terms = models.IntegerField(
        default=30,
        help_text="Payment terms in days"
    )
    delivery_terms = models.CharField(
        max_length=200,
        blank=True,
        help_text="Delivery terms and conditions"
    )
    validity_date = models.DateField(
        help_text="Quote expires on this date"
    )
    
    # Client communication tracking
    sent_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this quote was sent to client"
    )
    viewed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When client first viewed this quote"
    )
    response_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When client responded (accepted/rejected)"
    )
    
    # Team assignment and workflow
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_quotes',
        help_text="Employee who created this quote"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_quotes',
        help_text="Employee responsible for this quote"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_quotes',
        help_text="Manager who approved this quote (if approval required)"
    )
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.quote_number} - {self.client.name} - ${self.total_amount:,.2f}"
    
    def get_absolute_url(self):
        return reverse('quotes:quote_detail', kwargs={'quote_id': self.id})
    
    @property
    def is_expired(self):
        """Check if quote has passed its validity date"""
        return timezone.now().date() > self.validity_date
    
    @property
    def days_until_expiry(self):
        """Calculate days until quote expires"""
        if self.validity_date:
            delta = self.validity_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def can_be_accepted(self):
        """Determine if quote can still be accepted"""
        return (
            self.status in ['sent', 'viewed', 'under_review'] and 
            not self.is_expired
        )
    
    def calculate_totals(self):
        """
        Recalculate all financial totals based on quote items.
        This is the brain of your pricing system.
        """
        # Sum all line items
        self.subtotal = sum(
            item.total_price for item in self.items.all()
        )
        
        # Calculate discount
        self.discount_amount = (
            self.subtotal * self.discount_percentage / 100
        )
        
        # Calculate tax on discounted amount
        taxable_amount = self.subtotal - self.discount_amount
        self.tax_amount = taxable_amount * self.tax_rate / 100
        
        # Final total
        self.total_amount = taxable_amount + self.tax_amount
        
        self.save(update_fields=[
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount'
        ])
    
    def mark_as_sent(self):
        """Mark quote as sent and create CRM interaction"""
        self.status = 'sent'
        self.sent_date = timezone.now()
        self.save()
        
        # Create CRM interaction - this integrates with your existing system
        from crm.models import CustomerInteraction
        CustomerInteraction.objects.create(
            client=self.client,
            interaction_type='quote_sent',
            subject=f'Quote {self.quote_number} sent',
            notes=f'Quote for {self.title} - Total: ${self.total_amount:,.2f}',
            next_followup=timezone.now() + timezone.timedelta(days=3),
            created_by=self.created_by
        )
    
    def mark_as_accepted(self, accepted_by_user=None):
        """Handle quote acceptance workflow"""
        self.status = 'accepted'
        self.response_date = timezone.now()
        self.save()
        
        # Create CRM interaction
        from crm.models import CustomerInteraction
        CustomerInteraction.objects.create(
            client=self.client,
            interaction_type='quote_accepted',
            subject=f'Quote {self.quote_number} accepted!',
            notes=f'Client accepted quote for ${self.total_amount:,.2f}',
            created_by=accepted_by_user or self.created_by
        )
        
        # Update client analytics in your CRM
        self.client.total_value += self.total_amount
        self.client.save()
        
    def generate_access_token(self):
        """Generate secure access token for client portal."""
        import hashlib
        import uuid
        
        base_string = f"{self.id}-{self.client.email}-{uuid.uuid4()}"
        self.access_token = hashlib.sha256(base_string.encode()).hexdigest()[:32]
        self.save(update_fields=['access_token'])
        return self.access_token

    def track_client_view(self, ip_address=None):
        """Track when client views the quote."""
        self.view_count += 1
        self.last_viewed = timezone.now()
        if ip_address:
            self.client_ip = ip_address
        
        if self.status == 'sent':
            self.status = 'viewed'
            self.viewed_date = timezone.now()
        
        self.save(update_fields=['view_count', 'last_viewed', 'client_ip', 'status', 'viewed_date'])

    def check_approval_required(self):
        """Check if quote requires approval based on business rules."""
        reasons = []
        
        # High value quotes need approval
        if self.total_amount >= Decimal('10000.00'):
            reasons.append(f"High value quote: ${self.total_amount:,.2f}")
        
        # High discount quotes need approval
        if self.discount_percentage >= 20:
            reasons.append(f"High discount: {self.discount_percentage}%")
        
        # Low margin quotes need approval (if cost data available)
        if hasattr(self, 'calculate_profit_margin'):
            margin = self.calculate_profit_margin()
            if margin < 15:
                reasons.append(f"Low margin: {margin:.1f}%")
        
        if reasons:
            self.requires_approval = True
            self.approval_reason = "; ".join(reasons)
            self.save(update_fields=['requires_approval', 'approval_reason'])
            return True
        
        return False

    def schedule_followup(self, days=3):
        """Schedule automatic follow-up reminder."""
        self.next_followup = timezone.now() + timezone.timedelta(days=days)
        self.save(update_fields=['next_followup'])

    @property
    def is_overdue_followup(self):
        """Check if quote follow-up is overdue."""
        if not self.next_followup:
            return False
        return timezone.now() > self.next_followup and self.status in ['sent', 'viewed', 'under_review']

    @property
    def client_engagement_score(self):
        """Calculate client engagement score based on interactions."""
        score = 0
        
        # Base score for viewing
        if self.view_count > 0:
            score += min(self.view_count * 10, 50)  # Max 50 points for views
        
        # Bonus for multiple views
        if self.view_count > 3:
            score += 20
        
        # Points for status progression
        status_points = {
            'sent': 10,
            'viewed': 25,
            'under_review': 40,
            'accepted': 100,
            'rejected': 0
        }
        score += status_points.get(self.status, 0)
        
        # Points for feedback
        if self.client_feedback:
            score += 30
        
        # Time decay (newer interactions score higher)
        if self.last_viewed:
            days_ago = (timezone.now() - self.last_viewed).days
            if days_ago < 7:
                score += 15
            elif days_ago < 30:
                score += 5
        
        return min(score, 100)  # Cap at 100

class QuoteItem(models.Model):
    """
    Individual line items in a quote. Think of each QuoteItem as a single 
    product or service with its own pricing, quantity, and source information.
    """
    
    # Source types - where this item comes from
    SOURCE_CHOICES = [
        ('stock', 'In Stock'),                    # We have it ready
        ('order', 'Order from Supplier'),        # We'll order it
        ('direct', 'Direct from Supplier'),      # Supplier ships direct
        ('custom', 'Custom/Service Item'),       # Non-inventory item
    ]
    
    # Link to parent quote
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Product information
    product = models.ForeignKey(
        'inventory.Product',  # Links to your inventory system
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Leave blank for custom items"
    )
    
    # Line item details (can override product defaults)
    description = models.CharField(
        max_length=500,
        help_text="Description as it appears on quote"
    )
    detailed_specs = models.TextField(
        blank=True,
        help_text="Technical specifications for this item"
    )
    
    # Quantity and pricing
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity requested"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit"
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity × Unit Price"
    )
    
    # Cost tracking (for profit analysis)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Our cost per unit"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Markup percentage applied"
    )
    
    # Sourcing information
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='stock'
    )
    supplier = models.ForeignKey(
        'inventory.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Supplier for this item (if not from stock)"
    )
    supplier_lead_time = models.IntegerField(
        default=0,
        help_text="Lead time in days from supplier"
    )
    estimated_delivery = models.DateField(
        null=True,
        blank=True,
        help_text="When this item can be delivered"
    )
    
    # Line item notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this line item"
    )
    
    # Ordering for display
    sort_order = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['sort_order', 'id']
    
    def __str__(self):
        return f"{self.description} (Qty: {self.quantity})"
    
    def save(self, *args, **kwargs):
        """Auto-calculate total price and update quote totals"""
        # Calculate line total
        self.total_price = Decimal(str(self.quantity)) * self.unit_price
        
        # If linked to product, inherit some defaults
        if self.product and not self.description:
            self.description = self.product.quote_description or self.product.name
        
        super().save(*args, **kwargs)
        
        # Recalculate quote totals
        self.quote.calculate_totals()
    
    @property
    def profit_amount(self):
        """Calculate profit on this line item"""
        total_cost = Decimal(str(self.quantity)) * self.unit_cost
        return self.total_price - total_cost
    
    @property
    def profit_percentage(self):
        """Calculate profit percentage"""
        if self.unit_cost > 0:
            profit_per_unit = self.unit_price - self.unit_cost
            return (profit_per_unit / self.unit_cost) * 100
        return Decimal('0.00')

class QuoteRevision(models.Model):
    """
    Track quote changes over time. This is crucial for maintaining 
    client relationships and understanding negotiation patterns.
    """
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='revisions'
    )
    
    revision_number = models.IntegerField(default=1)
    change_summary = models.TextField(
        help_text="What changed in this revision"
    )
    previous_total = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    new_total = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-revision_number']
    
    def __str__(self):
        return f"{self.quote.quote_number} - Revision {self.revision_number}"

class QuoteTemplate(models.Model):
    """
    Reusable quote templates for common product bundles or services.
    This speeds up quote creation for standard offerings.
    """
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Default terms
    default_validity_days = models.IntegerField(default=30)
    default_payment_terms = models.IntegerField(default=30)
    
    # Template items (JSON structure for flexibility)
    template_items = models.JSONField(
        default=list,
        help_text="List of default items for this template"
    )
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class QuoteEnhancements(models.Model):
    """
    Additional fields to add to your existing Quote model.
    You can add these via Django migration.
    """
    
    # Client portal access
    access_token = models.CharField(
        max_length=64, 
        blank=True, 
        null=True,
        help_text="Secure token for client portal access"
    )
    
    # Enhanced tracking
    client_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        help_text="IP address when client viewed quote"
    )
    
    view_count = models.IntegerField(
        default=0,
        help_text="Number of times client viewed this quote"
    )
    
    last_viewed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time client viewed quote"
    )
    
    # Approval workflow
    requires_approval = models.BooleanField(
        default=False,
        help_text="Quote requires management approval before sending"
    )
    
    approval_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason why approval is required"
    )
    
    # Follow-up management
    next_followup = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to follow up on this quote"
    )
    
    followup_count = models.IntegerField(
        default=0,
        help_text="Number of follow-up attempts"
    )
    
    # Client feedback
    client_feedback = models.TextField(
        blank=True,
        help_text="Feedback received from client"
    )
    
    feedback_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When client provided feedback"
    )
    
    class Meta:
        abstract = True
