# quotes/client_portal_views.py
"""
Client Portal Views for Public Quote Access

These views allow clients to view, accept, and interact with quotes
without requiring authentication. They use secure tokens for access control.
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
import json
import logging

from .models import Quote
from crm.models import CustomerInteraction
from .email_utils import send_quote_notification

logger = logging.getLogger(__name__)

def quote_preview_public(request, quote_id, access_token):
    """
    Public quote preview accessible via secure token.
    This is the main client-facing view for quotes sent via email.
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Verify access token
    if not _verify_access_token(quote, access_token):
        return render(request, 'quotes/client_portal/access_denied.html', {
            'error': 'Invalid or expired access link. Please contact us for a new quote link.'
        })
    
    # Track that client viewed the quote
    if quote.status == 'sent' and not quote.viewed_date:
        quote.viewed_date = timezone.now()
        quote.status = 'viewed'
        quote.save(update_fields=['viewed_date', 'status'])
        
        # Create CRM interaction for tracking
        CustomerInteraction.objects.create(
            client=quote.client,
            interaction_type='quote_viewed',
            subject=f'Client viewed quote {quote.quote_number}',
            notes=f'Quote accessed via email link by {quote.client.name}',
            created_by=quote.created_by
        )
        
        # Notify internal team
        send_quote_notification(quote, {
            'old_status': 'sent',
            'new_status': 'viewed'
        })
    
    # Get quote items for display
    quote_items = quote.items.all().select_related('product', 'supplier')
    
    # Calculate additional information
    total_items = quote_items.count()
    estimated_delivery = None
    if quote_items.exists():
        # Find latest delivery date
        delivery_dates = [item.estimated_delivery for item in quote_items if item.estimated_delivery]
        if delivery_dates:
            estimated_delivery = max(delivery_dates)
    
    context = {
        'quote': quote,
        'quote_items': quote_items,
        'total_items': total_items,
        'estimated_delivery': estimated_delivery,
        'access_token': access_token,
        'can_accept': quote.can_be_accepted,
        'is_expired': quote.is_expired,
        'days_until_expiry': quote.days_until_expiry,
        'company_info': _get_company_info(),
        'page_title': f'Quote {quote.quote_number}',
    }
    
    return render(request, 'quotes/client_portal/quote_preview.html', context)

@require_http_methods(["GET", "POST"])
def quote_accept_public(request, quote_id, access_token):
    """
    Public quote acceptance endpoint.
    Allows clients to accept quotes without authentication.
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Verify access token
    if not _verify_access_token(quote, access_token):
        return render(request, 'quotes/client_portal/access_denied.html', {
            'error': 'Invalid or expired access link.'
        })
    
    # Check if quote can be accepted
    if not quote.can_be_accepted:
        return render(request, 'quotes/client_portal/quote_unavailable.html', {
            'quote': quote,
            'reason': 'expired' if quote.is_expired else 'status',
            'company_info': _get_company_info(),
        })
    
    if request.method == 'GET':
        # Show acceptance confirmation page
        context = {
            'quote': quote,
            'access_token': access_token,
            'company_info': _get_company_info(),
            'page_title': f'Accept Quote {quote.quote_number}',
        }
        return render(request, 'quotes/client_portal/quote_accept.html', context)
    
    elif request.method == 'POST':
        # Process quote acceptance
        try:
            with transaction.atomic():
                # Update quote status
                old_status = quote.status
                quote.status = 'accepted'
                quote.response_date = timezone.now()
                quote.save(update_fields=['status', 'response_date'])
                
                # Get client comments if provided
                client_comments = request.POST.get('comments', '').strip()
                
                # Create CRM interaction
                interaction_notes = f'Quote {quote.quote_number} accepted by client via online portal'
                if client_comments:
                    interaction_notes += f'. Client comments: {client_comments}'
                
                CustomerInteraction.objects.create(
                    client=quote.client,
                    interaction_type='quote_accepted',
                    subject=f'Quote {quote.quote_number} accepted!',
                    notes=interaction_notes,
                    created_by=quote.created_by
                )
                
                # Update client analytics
                quote.client.total_value += quote.total_amount
                quote.client.total_orders += 1
                if quote.client.status == 'prospect':
                    quote.client.status = 'client'
                quote.client.save()
                
                # Send notifications to internal team
                send_quote_notification(quote, {
                    'old_status': old_status,
                    'new_status': 'accepted',
                    'client_comments': client_comments
                })
                
                logger.info(f"Quote {quote.quote_number} accepted by {quote.client.name}")
                
                # Show success page
                context = {
                    'quote': quote,
                    'company_info': _get_company_info(),
                    'client_comments': client_comments,
                    'page_title': 'Quote Accepted Successfully',
                }
                return render(request, 'quotes/client_portal/quote_accepted.html', context)
                
        except Exception as e:
            logger.error(f"Error accepting quote {quote.quote_number}: {str(e)}")
            context = {
                'quote': quote,
                'error': 'An error occurred while processing your acceptance. Please contact us directly.',
                'company_info': _get_company_info(),
            }
            return render(request, 'quotes/client_portal/quote_error.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def quote_feedback_public(request, quote_id, access_token):
    """
    Allow clients to provide feedback on quotes without accepting.
    This helps improve future quotes and maintain client relationships.
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Verify access token
    if not _verify_access_token(quote, access_token):
        return JsonResponse({'success': False, 'error': 'Invalid access'})
    
    try:
        data = json.loads(request.body)
        feedback_type = data.get('type')  # 'question', 'concern', 'modification_request'
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message is required'})
        
        # Create CRM interaction for the feedback
        CustomerInteraction.objects.create(
            client=quote.client,
            interaction_type='feedback',
            subject=f'Client feedback on quote {quote.quote_number}',
            notes=f'Feedback type: {feedback_type}. Message: {message}',
            created_by=quote.created_by,
            next_followup=timezone.now() + timezone.timedelta(days=1)  # Follow up tomorrow
        )
        
        # Send email notification to assigned user
        from django.core.mail import send_mail
        if quote.assigned_to and quote.assigned_to.email:
            subject = f"Client Feedback on Quote {quote.quote_number}"
            email_message = f"""
{quote.client.name} has provided feedback on Quote {quote.quote_number}:

Type: {feedback_type.replace('_', ' ').title()}
Message: {message}

Quote Details:
- Amount: ${quote.total_amount:,.2f}
- Status: {quote.get_status_display()}
- Valid Until: {quote.validity_date.strftime('%B %d, %Y')}

Please follow up with the client to address their feedback.

View Quote: {request.build_absolute_uri(reverse('quotes:quote_detail', args=[quote.id]))}
            """
            
            send_mail(
                subject=subject,
                message=email_message,
                from_email=_get_company_info()['email'],
                recipient_list=[quote.assigned_to.email],
                fail_silently=True
            )
        
        logger.info(f"Feedback received for quote {quote.quote_number} from {quote.client.name}")
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback! We will follow up with you shortly.'
        })
        
    except Exception as e:
        logger.error(f"Error processing feedback for quote {quote.quote_number}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while submitting your feedback. Please contact us directly.'
        })

def quote_download_public(request, quote_id, access_token):
    """
    Allow clients to download PDF version of their quote.
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Verify access token
    if not _verify_access_token(quote, access_token):
        return render(request, 'quotes/client_portal/access_denied.html')
    
    # Track download activity
    CustomerInteraction.objects.create(
        client=quote.client,
        interaction_type='quote_download',
        subject=f'Quote {quote.quote_number} PDF downloaded',
        notes=f'Client downloaded PDF via portal',
        created_by=quote.created_by
    )
    
    # Generate and return PDF
    from .views import generate_quote_pdf
    return generate_quote_pdf(request, quote_id)

def quote_contact_public(request, quote_id, access_token):
    """
    Contact form for clients to ask questions about specific quotes.
    """
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Verify access token
    if not _verify_access_token(quote, access_token):
        return render(request, 'quotes/client_portal/access_denied.html')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not all([name, email, message]):
            messages.error(request, 'Please fill in all required fields.')
        else:
            # Create CRM interaction
            contact_info = f"Name: {name}, Email: {email}"
            if phone:
                contact_info += f", Phone: {phone}"
            
            CustomerInteraction.objects.create(
                client=quote.client,
                interaction_type='inquiry',
                subject=f'Contact form submission regarding quote {quote.quote_number}',
                notes=f'{contact_info}. Message: {message}',
                created_by=quote.created_by,
                next_followup=timezone.now() + timezone.timedelta(hours=4)  # Follow up in 4 hours
            )
            
            # Send email to assigned user
            from django.core.mail import send_mail
            if quote.assigned_to and quote.assigned_to.email:
                subject = f"Contact Form: Quote {quote.quote_number}"
                email_message = f"""
New contact form submission regarding Quote {quote.quote_number}:

From: {name} ({email})
{f'Phone: {phone}' if phone else ''}

Message:
{message}

Quote: {quote.quote_number} - ${quote.total_amount:,.2f}
Client: {quote.client.name}

Please respond promptly to maintain client engagement.
                """
                
                send_mail(
                    subject=subject,
                    message=email_message,
                    from_email=_get_company_info()['email'],
                    recipient_list=[quote.assigned_to.email],
                    fail_silently=True
                )
            
            messages.success(request, 'Thank you for your message! We will respond within 4 hours.')
            return HttpResponseRedirect(
                reverse('quotes:quote_preview_public', args=[quote_id, access_token])
            )
    
    context = {
        'quote': quote,
        'access_token': access_token,
        'company_info': _get_company_info(),
        'page_title': f'Contact Us - Quote {quote.quote_number}',
    }
    
    return render(request, 'quotes/client_portal/quote_contact.html', context)

# Helper functions

def _verify_access_token(quote, provided_token):
    """
    Verify that the provided access token is valid for the quote.
    Implements basic security for public access.
    """
    if not provided_token or len(provided_token) != 32:
        return False
    
    # Check if quote has stored access token
    if hasattr(quote, 'access_token') and quote.access_token:
        return quote.access_token == provided_token
    
    # Fallback: generate expected token for backward compatibility
    import hashlib
    base_string = f"{quote.id}-{quote.client.email}-{quote.created_at.isoformat()}"
    expected_token = hashlib.sha256(base_string.encode()).hexdigest()[:32]
    
    return expected_token == provided_token

def _get_company_info():
    """Get company information for templates."""
    from django.conf import settings
    
    return {
        'name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
        'address': getattr(settings, 'COMPANY_ADDRESS', 'Harare, Zimbabwe'),
        'phone': getattr(settings, 'COMPANY_PHONE', '+263 XX XXX XXXX'),
        'email': getattr(settings, 'COMPANY_EMAIL', 'info@blitztechelectronics.co.zw'),
        'website': getattr(settings, 'COMPANY_WEBSITE', 'www.blitztechelectronics.co.zw'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@blitztechelectronics.co.zw'),
    }