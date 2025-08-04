"""
Quote Engine Signal Handlers for CRM Integration

Signal handlers are like the nervous system of your application - they detect when
important events happen and automatically trigger appropriate responses throughout
your system. This creates seamless integration without tight coupling between modules.

Think of signals as having a team of attentive assistants who notice when something
important happens (like a quote being accepted) and immediately inform everyone else
who needs to know (like the CRM system, accounting, and inventory management).
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Quote, QuoteItem, QuoteRevision
from crm.models import Client, CustomerInteraction
from core.utils import create_notification
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Quote)
def handle_quote_lifecycle_changes(sender, instance, created, **kwargs):
    """
    This signal handler orchestrates all the business processes that should happen
    when quotes are created or updated. It's like having a smart coordinator who
    knows exactly what needs to happen when a quote changes status.
    
    The beauty of using signals for this coordination is that it keeps our business
    logic centralized and ensures that important processes never get forgotten,
    even when quotes are updated through different parts of the system.
    """
    
    quote = instance
    
    if created:
        # When a new quote is created, we need to establish the foundation
        # for tracking this opportunity in our CRM system
        _handle_new_quote_creation(quote)
    else:
        # When an existing quote is updated, we need to detect what changed
        # and respond appropriately
        _handle_quote_status_changes(quote)
        _handle_quote_value_changes(quote)

def _handle_new_quote_creation(quote):
    """
    When a new quote is created, this function ensures that all the supporting
    infrastructure is properly established. Think of it as the intake process
    for a new sales opportunity.
    """
    
    try:
        with transaction.atomic():
            # Create the initial CRM interaction that establishes this quote
            # in the customer's timeline
            CustomerInteraction.objects.create(
                client=quote.client,
                interaction_type='quote_draft',
                subject=f'Quote {quote.quote_number} created',
                notes=f'New quote created for {quote.title} - Value: ${quote.total_amount:,.2f}',
                created_by=quote.created_by,
                # Automatically schedule a follow-up based on quote urgency
                next_followup=_calculate_initial_followup_date(quote)
            )
            
            # Update the client's lead score based on quote activity
            # This helps prioritize clients who are actively requesting quotes
            _update_client_lead_score_for_quote_activity(quote.client)
            
            # Notify the assigned team member about the new quote
            if quote.assigned_to and quote.assigned_to != quote.created_by:
                create_notification(
                    user=quote.assigned_to,
                    title="New Quote Assigned",
                    message=f"Quote {quote.quote_number} for {quote.client.name} has been assigned to you. Value: ${quote.total_amount:,.2f}",
                    notification_type="info"
                )
            
            # If this is a high-value quote, notify management
            if quote.total_amount >= Decimal('10000.00'):
                _notify_management_of_high_value_quote(quote)
            
            logger.info(f"Quote creation workflow completed for {quote.quote_number}")
            
    except Exception as e:
        # If anything goes wrong in our coordination process, we log it
        # but don't prevent the quote from being created
        logger.error(f"Error in quote creation workflow for {quote.quote_number}: {str(e)}")

def _handle_quote_status_changes(quote):
    """
    This function detects and responds to quote status changes. Different statuses
    trigger different business processes, just like how different stages in a
    sales process require different actions from your team.
    """
    
    # We need to check if the status actually changed by looking at the
    # previous version of the quote from the database
    try:
        if quote.pk:  # Only for existing quotes
            previous_quote = Quote.objects.get(pk=quote.pk)
            
            # Compare the current status with what's in the database
            if hasattr(previous_quote, 'status') and previous_quote.status != quote.status:
                _process_status_change(quote, previous_quote.status, quote.status)
                
    except Quote.DoesNotExist:
        # This shouldn't happen, but if it does, we log it and continue
        logger.warning(f"Could not find previous version of quote {quote.quote_number}")

def _process_status_change(quote, old_status, new_status):
    """
    Each status transition triggers specific business processes. This is where
    we codify the business rules about what should happen when quotes move
    through different stages of the sales pipeline.
    """
    
    try:
        with transaction.atomic():
            # Create a CRM interaction for every status change
            # This creates a complete audit trail of the quote's journey
            interaction_notes = f'Quote status changed from {old_status} to {new_status}'
            
            # Add context-specific information based on the new status
            if new_status == 'sent':
                interaction_notes += f'. Quote sent to client at {quote.client.email}'
                _handle_quote_sent(quote)
                
            elif new_status == 'accepted':
                interaction_notes += f'. Client accepted quote for ${quote.total_amount:,.2f}'
                _handle_quote_accepted(quote)
                
            elif new_status == 'rejected':
                interaction_notes += '. Client declined the quote'
                _handle_quote_rejected(quote)
                
            elif new_status == 'expired':
                interaction_notes += '. Quote expired without client response'
                _handle_quote_expired(quote)
            
            # Record the status change in the client's interaction history
            CustomerInteraction.objects.create(
                client=quote.client,
                interaction_type='quote',
                subject=f'Quote {quote.quote_number} - {new_status.title()}',
                notes=interaction_notes,
                created_by=quote.created_by or quote.assigned_to
            )
            
            logger.info(f"Status change processed for {quote.quote_number}: {old_status} -> {new_status}")
            
    except Exception as e:
        logger.error(f"Error processing status change for {quote.quote_number}: {str(e)}")

def _handle_quote_sent(quote):
    """
    When a quote is sent to a client, we initiate the follow-up tracking
    process and update client engagement metrics.
    """
    
    # Schedule automatic follow-up reminders
    follow_up_days = 3  # Follow up in 3 days if no response
    if quote.total_amount >= Decimal('5000.00'):
        follow_up_days = 2  # Faster follow-up for high-value quotes
    
    # Update the quote's follow-up schedule
    quote.next_followup = timezone.now() + timezone.timedelta(days=follow_up_days)
    quote.save(update_fields=['next_followup'])
    
    # Update client's last contacted date
    quote.client.last_contacted = timezone.now()
    quote.client.save(update_fields=['last_contacted'])

def _handle_quote_accepted(quote):
    """
    Quote acceptance triggers several important business processes that
    transform the quote from an opportunity into active business.
    """
    
    # Update client analytics to reflect the successful quote
    client = quote.client
    client.total_value += quote.total_amount
    client.total_orders += 1
    
    # Recalculate average order value
    if client.total_orders > 0:
        client.average_order_value = client.total_value / client.total_orders
    
    # Update client status if they were a prospect
    if client.status in ['lead', 'prospect']:
        client.status = 'client'
    
    client.save()
    
    # Update lead scoring based on successful conversion
    client.calculate_lead_score()
    
    # Notify the sales team about the success
    create_notification(
        user=quote.assigned_to or quote.created_by,
        title="Quote Accepted!",
        message=f"🎉 {quote.client.name} accepted quote {quote.quote_number} for ${quote.total_amount:,.2f}",
        notification_type="success"
    )
    
    # For high-value quotes, notify management
    if quote.total_amount >= Decimal('10000.00'):
        _notify_management_of_quote_acceptance(quote)

def _handle_quote_rejected(quote):
    """
    When a quote is rejected, we want to learn from the experience and
    maintain the relationship for future opportunities.
    """
    
    # Schedule a follow-up to understand why the quote was rejected
    # and maintain the relationship
    follow_up_date = timezone.now() + timezone.timedelta(days=30)
    
    CustomerInteraction.objects.create(
        client=quote.client,
        interaction_type='followup',
        subject='Follow up on rejected quote',
        notes=f'Follow up with {quote.client.name} to understand rejection reasons and explore future opportunities',
        next_followup=follow_up_date,
        created_by=quote.assigned_to or quote.created_by
    )

def _calculate_initial_followup_date(quote):
    """
    Calculate when we should first follow up on a new quote based on
    business rules and quote characteristics.
    """
    
    base_days = 7  # Default follow-up in one week
    
    # Adjust based on quote value - higher value quotes get faster follow-up
    if quote.total_amount >= Decimal('10000.00'):
        base_days = 3
    elif quote.total_amount >= Decimal('5000.00'):
        base_days = 5
    
    # Adjust based on client priority
    if quote.client.priority == 'vip':
        base_days = max(1, base_days - 2)
    elif quote.client.priority == 'high':
        base_days = max(2, base_days - 1)
    
    return timezone.now() + timezone.timedelta(days=base_days)

def _update_client_lead_score_for_quote_activity(client):
    """
    Quote activity is a strong indicator of client engagement, so we
    update the lead score to reflect this positive signal.
    """
    
    # Quote requests indicate high engagement
    engagement_boost = 10
    
    # Recent quote activity gets a bigger boost
    recent_quotes = Quote.objects.filter(
        client=client,
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()
    
    if recent_quotes > 1:
        engagement_boost += 5  # Multiple recent quotes = very engaged client
    
    # Apply the boost to the client's lead score
    current_score = client.lead_score or 0
    new_score = min(100, current_score + engagement_boost)
    
    client.lead_score = new_score
    client.save(update_fields=['lead_score'])

@receiver(post_save, sender=QuoteItem)
def handle_quote_item_changes(sender, instance, created, **kwargs):
    """
    When quote items are added, removed, or modified, we need to update
    related systems and maintain data consistency. This is like having
    an inventory manager who tracks every change to ensure accuracy.
    """
    
    quote_item = instance
    quote = quote_item.quote
    
    try:
        # Recalculate quote totals whenever items change
        quote.calculate_totals()
        
        # If this item references inventory, we might want to reserve
        # or unreserve stock (this would integrate with your inventory system)
        if quote_item.product and quote_item.source_type == 'stock':
            _handle_inventory_implications(quote_item, created)
        
        # Log the change for audit purposes
        change_type = 'added' if created else 'modified'
        logger.info(f"Quote item {change_type} in {quote.quote_number}: {quote_item.description}")
        
    except Exception as e:
        logger.error(f"Error handling quote item change: {str(e)}")

def _handle_inventory_implications(quote_item, is_new_item):
    """
    This function would integrate with your inventory system to handle
    stock reservations when quotes reference inventory items.
    """
    
    # This is where you would implement inventory integration
    # For now, we'll just log the intention
    if is_new_item:
        logger.info(f"Would reserve {quote_item.quantity} units of {quote_item.product.sku}")
    else:
        logger.info(f"Would update reservation for {quote_item.product.sku}")

@receiver(post_delete, sender=QuoteItem)
def handle_quote_item_deletion(sender, instance, **kwargs):
    """
    When quote items are deleted, we need to clean up any related
    reservations or dependencies.
    """
    
    quote_item = instance
    
    try:
        # If the quote still exists, recalculate its totals
        if quote_item.quote_id:
            quote = Quote.objects.get(id=quote_item.quote_id)
            quote.calculate_totals()
        
        # Release any inventory reservations
        if quote_item.product and quote_item.source_type == 'stock':
            logger.info(f"Would release reservation for {quote_item.quantity} units of {quote_item.product.sku}")
        
    except Quote.DoesNotExist:
        # The quote itself was probably deleted, which is fine
        pass
    except Exception as e:
        logger.error(f"Error handling quote item deletion: {str(e)}")

def _notify_management_of_high_value_quote(quote):
    """
    High-value quotes require management attention, so we automatically
    notify appropriate managers when these opportunities arise.
    """
    
    from django.contrib.auth.models import User
    
    try:
        # Find users who should be notified about high-value quotes
        managers = User.objects.filter(
            profile__user_type__in=['blitzhub_admin', 'it_admin'],
            is_active=True
        )
        
        for manager in managers:
            create_notification(
                user=manager,
                title="High-Value Quote Created",
                message=f"High-value quote {quote.quote_number} created for {quote.client.name} - ${quote.total_amount:,.2f}",
                notification_type="warning"  # Warning to indicate importance
            )
            
    except Exception as e:
        logger.error(f"Error notifying management of high-value quote: {str(e)}")

def _notify_management_of_quote_acceptance(quote):
    """
    Successful high-value quote closures are celebration-worthy events
    that management should know about immediately.
    """
    
    from django.contrib.auth.models import User
    
    try:
        managers = User.objects.filter(
            profile__user_type__in=['blitzhub_admin', 'it_admin'],
            is_active=True
        )
        
        for manager in managers:
            create_notification(
                user=manager,
                title="High-Value Quote Accepted!",
                message=f"🎉 Excellent work! {quote.client.name} accepted quote {quote.quote_number} for ${quote.total_amount:,.2f}",
                notification_type="success"
            )
            
    except Exception as e:
        logger.error(f"Error notifying management of quote acceptance: {str(e)}")
