from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
import uuid

class Client(models.Model):
    """Enhanced client model with analytics and business intelligence"""
    
    STATUS_CHOICES = [
        ('lead', 'Lead'),
        ('prospect', 'Prospect'),
        ('client', 'Active Client'),
        ('inactive', 'Inactive'),
        ('lost', 'Lost'),
    ]
    
    CUSTOMER_TYPE_CHOICES = [
        ('walk_in', 'Walk-in Customer'),
        ('corporate', 'Corporate Client'),
        ('institutional', 'Institutional Client'),
        ('government', 'Government Client'),
        ('reseller', 'Reseller/Partner'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('vip', 'VIP Client'),
    ]
    
    # Basic Information
    client_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Company Information
    company = models.CharField(max_length=200, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., 1-10, 11-50, 51-200, 200+")
    
    # Address Information
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='Zimbabwe')
    
    # Business Classification
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='lead')
    customer_type = models.CharField(max_length=50, choices=CUSTOMER_TYPE_CHOICES, default='walk_in')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Financial Information
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Credit limit in USD")
    payment_terms = models.IntegerField(default=30, help_text="Payment terms in days")
    tax_number = models.CharField(max_length=50, blank=True, null=True, help_text="VAT/Tax registration number")
    currency_preference = models.CharField(max_length=3, default='USD', choices=[('USD', 'US Dollar'), ('ZWG', 'Zimbabwe Gold')])
    
    # Analytics Fields
    total_orders = models.IntegerField(default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Total value of all orders")
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Average profit margin %")
    
    # Interaction Tracking
    last_contacted = models.DateTimeField(blank=True, null=True)
    last_order_date = models.DateTimeField(blank=True, null=True)
    followup_date = models.DateTimeField(blank=True, null=True)
    
    # Lead Scoring
    lead_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    conversion_probability = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Conversion probability %")
    
    # Notes and Additional Info
    notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True, help_text="Internal notes not visible to client")
    tags = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated tags")
    
    # Source Tracking
    source = models.CharField(max_length=100, blank=True, null=True, help_text="How did they find us?")
    referral_source = models.CharField(max_length=200, blank=True, null=True)
    marketing_campaign = models.CharField(max_length=200, blank=True, null=True)
    
    # Assigned Team
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_clients')
    account_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_clients')
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    preferred_payment_method = models.CharField(
        max_length=50, 
        choices=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('lay_bye', 'Lay Bye'),
            ('credit_terms', 'Credit Terms'),
        ],
        default='cash'
    )
    
    default_markup_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        help_text="Default markup percentage for this client"
    )
    requires_quote_approval = models.BooleanField(
        default=False,
        help_text="Does this client require management approval for quotes?"
    )
    quote_validity_days = models.IntegerField(
        default=30,
        help_text="Default quote validity period in days"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'customer_type']),
            models.Index(fields=['country', 'city']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['last_contacted']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.company})" if self.company else self.name
    
    def get_absolute_url(self):
        return reverse('crm:client_detail', kwargs={'client_id': self.id})
    
    @property
    def full_address(self):
        """Get formatted full address"""
        address_parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.province,
            self.postal_code,
            self.country
        ]
        return ', '.join([part for part in address_parts if part])
    
    @property
    def days_since_last_contact(self):
        """Calculate days since last contact"""
        if self.last_contacted:
            return (timezone.now() - self.last_contacted).days
        return None
    
    @property
    def days_since_last_order(self):
        """Calculate days since last order"""
        if self.last_order_date:
            return (timezone.now() - self.last_order_date).days
        return None
    
    @property
    def is_overdue_followup(self):
        """Check if follow-up is overdue"""
        if self.followup_date:
            return timezone.now() > self.followup_date
        return False
    
    @property
    def tag_list(self):
        """Get tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def calculate_lead_score(self):
        """Calculate lead score based on various factors"""
        score = 0
        
        # Company size scoring
        if self.company_size:
            size_scores = {'1-10': 10, '11-50': 20, '51-200': 30, '200+': 40}
            score += size_scores.get(self.company_size, 0)
        
        # Interaction frequency
        recent_interactions = self.customerinteraction_set.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        score += min(recent_interactions * 5, 25)
        
        # Customer type scoring
        type_scores = {'corporate': 20, 'institutional': 25, 'government': 30, 'reseller': 15, 'walk_in': 5}
        score += type_scores.get(self.customer_type, 0)
        
        # Website interaction
        if self.website:
            score += 5
        
        self.lead_score = min(score, 100)
        self.save(update_fields=['lead_score'])
        return self.lead_score
    
    def update_analytics(self):
        """Update analytics fields based on orders and interactions"""
        # This would be connected to order data when implemented
        # For now, we'll update based on interactions
        interactions = self.customerinteraction_set.all()
        
        if interactions.exists():
            self.last_contacted = interactions.order_by('-created_at').first().created_at
        
        # Calculate conversion probability based on interactions and lead score
        if self.status == 'lead':
            probability = min((self.lead_score + interactions.count() * 2), 100)
            self.conversion_probability = probability
        elif self.status == 'prospect':
            self.conversion_probability = 75
        elif self.status == 'client':
            self.conversion_probability = 100
        else:
            self.conversion_probability = 0
        
        self.save(update_fields=['last_contacted', 'conversion_probability'])


class CustomerInteraction(models.Model):
    """Track all interactions with customers"""
    
    INTERACTION_TYPES = [
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('meeting', 'In-Person Meeting'),
        ('video_call', 'Video Call'),
        ('visit', 'Site Visit'),
        ('quote', 'Quote Sent'),
        ('proposal', 'Proposal Sent'),
        ('order', 'Order Placed'),
        ('complaint', 'Complaint'),
        ('support', 'Support Request'),
        ('followup', 'Follow-up'),
        ('created', 'Record Created'),
        ('updated', 'Record Updated'),
        ('followup_completed', 'Follow-up Completed'),
        ('quote_requested', 'Quote Requested'),
        ('quote_draft', 'Quote Draft Created'),
        ('quote_sent', 'Quote Sent to Client'),
        ('quote_viewed', 'Quote Viewed by Client'),
        ('quote_accepted', 'Quote Accepted'),
        ('quote_rejected', 'Quote Rejected'),
        ('quote_expired', 'Quote Expired'),
        ('quote_revised', 'Quote Revised'),
    ]
    
    OUTCOME_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
        ('no_response', 'No Response'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    
    # Interaction Details
    subject = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField()
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, null=True)
    
    # Follow-up Planning
    next_followup = models.DateTimeField(blank=True, null=True)
    followup_notes = models.TextField(blank=True, null=True)
    
    # Additional Context
    duration_minutes = models.IntegerField(blank=True, null=True, help_text="Duration in minutes")
    participants = models.CharField(max_length=500, blank=True, null=True, help_text="Other participants")
    attachments = models.FileField(upload_to='crm/interactions/', blank=True, null=True)
    
    # Audit Fields
    is_completed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'interaction_type']),
            models.Index(fields=['next_followup']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.client.name} - {self.get_interaction_type_display()} ({self.created_at.strftime('%Y-%m-%d')})"
    
    @property
    def is_followup_due(self):
        """Check if follow-up is due"""
        if self.next_followup:
            return timezone.now() >= self.next_followup
        return False
    
    @property
    def is_followup_overdue(self):
        """Check if follow-up is overdue"""
        if self.next_followup:
            return timezone.now() > self.next_followup
        return False


class Deal(models.Model):
    """Track sales opportunities and deals"""
    
    STAGE_CHOICES = [
        ('prospecting', 'Prospecting'),
        ('qualification', 'Qualification'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    deal_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    # Deal Details
    description = models.TextField(blank=True, null=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, help_text="Expected deal value")
    currency = models.CharField(max_length=3, default='USD')
    
    # Sales Process
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='prospecting')
    probability = models.IntegerField(default=10, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Win probability %")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Timeline
    expected_close_date = models.DateField(blank=True, null=True)
    actual_close_date = models.DateField(blank=True, null=True)
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tracking
    source = models.CharField(max_length=100, blank=True, null=True)
    competitor = models.CharField(max_length=200, blank=True, null=True)
    loss_reason = models.TextField(blank=True, null=True, help_text="Reason if deal is lost")
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_deals')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stage', 'assigned_to']),
            models.Index(fields=['expected_close_date']),
            models.Index(fields=['client', 'stage']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.client.name}"
    
    @property
    def weighted_value(self):
        """Calculate weighted value based on probability"""
        return (self.value * self.probability) / 100
    
    @property
    def days_until_close(self):
        """Days until expected close date"""
        if self.expected_close_date:
            return (self.expected_close_date - timezone.now().date()).days
        return None
    
    @property
    def is_overdue(self):
        """Check if deal is overdue"""
        if self.expected_close_date:
            return timezone.now().date() > self.expected_close_date
        return False


class Task(models.Model):
    """Track tasks and to-dos related to clients or deals"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Relationships
    client = models.ForeignKey(Client, on_delete=models.CASCADE, blank=True, null=True)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, blank=True, null=True)
    
    # Task Details
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timeline
    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['due_date', '-priority']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['client', 'status']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.due_date and self.status != 'completed':
            return timezone.now() > self.due_date
        return False
    
    @property
    def days_until_due(self):
        """Days until due date"""
        if self.due_date:
            return (self.due_date - timezone.now()).days
        return None
    
    def mark_completed(self):
        """Mark task as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class ClientNote(models.Model):
    """Additional notes and attachments for clients"""
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Attachments
    attachment = models.FileField(upload_to='crm/notes/', blank=True, null=True)
    
    # Privacy
    is_private = models.BooleanField(default=False, help_text="Only visible to assigned team members")
    
    # Audit Fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.client.name} - {self.title}"


class CRMSettings(models.Model):
    """CRM-specific settings and configuration"""
    
    # Lead Scoring Configuration
    lead_scoring_enabled = models.BooleanField(default=True)
    auto_assign_leads = models.BooleanField(default=False)
    
    # Follow-up Settings
    default_followup_days = models.IntegerField(default=7)
    followup_reminder_hours = models.IntegerField(default=24)
    
    # Analytics Settings
    analytics_retention_days = models.IntegerField(default=365)
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    overdue_followup_alerts = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "CRM Settings"
        verbose_name_plural = "CRM Settings"
    
    def __str__(self):
        return "CRM Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings


# Signal handlers for automatic updates
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=CustomerInteraction)
def update_client_on_interaction(sender, instance, created, **kwargs):
    """Update client analytics when interaction is created/updated"""
    if created:
        client = instance.client
        client.last_contacted = instance.created_at
        if instance.next_followup:
            client.followup_date = instance.next_followup
        
        # Recalculate lead score
        client.calculate_lead_score()
        client.update_analytics()

@receiver(post_save, sender=Deal)
def update_client_on_deal(sender, instance, created, **kwargs):
    """Update client when deal is created/updated"""
    if instance.stage == 'closed_won':
        # Update client status and value
        client = instance.client
        if client.status == 'lead' or client.status == 'prospect':
            client.status = 'client'
        
        client.total_orders += 1
        client.total_value += instance.value
        client.last_order_date = timezone.now()
        
        if client.total_orders > 0:
            client.average_order_value = client.total_value / client.total_orders
        
        client.save()

@receiver(post_save, sender=Task)
def create_task_notification(sender, instance, created, **kwargs):
    """Create notification when task is assigned"""
    if created and instance.assigned_to:
        from core.utils import create_notification
        create_notification(
            user=instance.assigned_to,
            title=f"New Task Assigned: {instance.title}",
            message=f"You have been assigned a new task related to {instance.client.name if instance.client else 'general'}",
            notification_type="info"
        )
