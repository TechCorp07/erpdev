# quotes/email_utils.py
"""
Professional Email System for Quote Management

This module handles all email-related functionality for the quote system,
providing professional, branded communications that enhance customer relationships.
"""

from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from io import BytesIO
import logging
import uuid

logger = logging.getLogger(__name__)

class QuoteEmailService:
    """
    Professional email service for quote communications.
    Handles all email templates, attachments, and delivery tracking.
    """
    
    def __init__(self):
        self.connection = get_connection(fail_silently=False)
    
    def send_quote_to_client(self, quote, request=None, custom_message=None):
        """
        Send a professional quote email to the client with PDF attachment.
        
        This creates a branded email experience that reflects your company's
        professionalism and makes it easy for clients to respond.
        """
        try:
            # Generate unique access token for client portal
            access_token = self._generate_access_token(quote)
            
            # Prepare email context
            context = {
                'quote': quote,
                'client': quote.client,
                'company_info': self._get_company_info(),
                'custom_message': custom_message,
                'access_token': access_token,
                'preview_url': self._build_preview_url(quote, access_token, request),
                'accept_url': self._build_accept_url(quote, access_token, request),
                'sender': quote.created_by,
                'sent_date': timezone.now(),
            }
            
            # Render email templates
            subject = f"Quote {quote.quote_number} from {context['company_info']['name']}"
            
            # HTML version for modern email clients
            html_content = render_to_string('quotes/emails/quote_email.html', context)
            
            # Text version for compatibility
            text_content = render_to_string('quotes/emails/quote_email.txt', context)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self._get_from_email(),
                to=[quote.client.email],
                cc=self._get_cc_emails(quote),
                reply_to=[quote.created_by.email] if quote.created_by.email else [],
                connection=self.connection
            )
            
            # Attach HTML version
            email.attach_alternative(html_content, "text/html")
            
            # Generate and attach PDF
            pdf_buffer = self._generate_quote_pdf(quote, request)
            if pdf_buffer:
                filename = f"Quote_{quote.quote_number}_{quote.client.name.replace(' ', '_')}.pdf"
                email.attach(filename, pdf_buffer.getvalue(), 'application/pdf')
            
            # Send email
            result = email.send()
            
            if result:
                # Update quote status and tracking
                self._update_quote_after_send(quote, access_token)
                
                # Log success
                logger.info(f"Quote {quote.quote_number} emailed successfully to {quote.client.email}")
                
                return {
                    'success': True,
                    'message': f'Quote sent successfully to {quote.client.email}',
                    'access_token': access_token
                }
            else:
                raise Exception("Email sending failed")
                
        except Exception as e:
            logger.error(f"Failed to send quote {quote.quote_number}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_quote_status_notification(self, quote, status_change):
        """
        Send internal notifications when quote status changes.
        Keeps the team informed about important quote developments.
        """
        try:
            # Determine recipients based on quote assignment and status
            recipients = self._get_status_notification_recipients(quote, status_change)
            
            if not recipients:
                return {'success': True, 'message': 'No notifications needed'}
            
            context = {
                'quote': quote,
                'status_change': status_change,
                'company_info': self._get_company_info(),
                'timestamp': timezone.now(),
            }
            
            subject = f"Quote {quote.quote_number} - {status_change['new_status'].title()}"
            
            # Use internal notification template
            html_content = render_to_string('quotes/emails/status_notification.html', context)
            text_content = render_to_string('quotes/emails/status_notification.txt', context)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self._get_from_email(),
                to=recipients,
                connection=self.connection
            )
            
            email.attach_alternative(html_content, "text/html")
            result = email.send()
            
            logger.info(f"Status notification sent for quote {quote.quote_number}")
            return {'success': True, 'message': 'Notification sent'}
            
        except Exception as e:
            logger.error(f"Failed to send status notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_quote_reminder(self, quote, reminder_type='follow_up'):
        """
        Send follow-up reminders for quotes that need attention.
        Helps maintain engagement without being pushy.
        """
        try:
            context = {
                'quote': quote,
                'reminder_type': reminder_type,
                'company_info': self._get_company_info(),
                'client': quote.client,
                'days_since_sent': (timezone.now().date() - quote.sent_date.date()).days if quote.sent_date else 0,
                'expires_in': quote.days_until_expiry,
            }
            
            # Choose appropriate subject based on reminder type
            if reminder_type == 'follow_up':
                subject = f"Following up on Quote {quote.quote_number}"
            elif reminder_type == 'expiring':
                subject = f"Quote {quote.quote_number} expires soon"
            else:
                subject = f"Regarding Quote {quote.quote_number}"
            
            html_content = render_to_string(f'quotes/emails/reminder_{reminder_type}.html', context)
            text_content = render_to_string(f'quotes/emails/reminder_{reminder_type}.txt', context)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self._get_from_email(),
                to=[quote.client.email],
                reply_to=[quote.assigned_to.email] if quote.assigned_to and quote.assigned_to.email else [],
                connection=self.connection
            )
            
            email.attach_alternative(html_content, "text/html")
            result = email.send()
            
            if result:
                # Create CRM interaction
                from crm.models import CustomerInteraction
                CustomerInteraction.objects.create(
                    client=quote.client,
                    interaction_type='email',
                    subject=subject,
                    notes=f'{reminder_type.title()} reminder sent for quote {quote.quote_number}',
                    created_by=quote.assigned_to or quote.created_by,
                    next_followup=timezone.now() + timezone.timedelta(days=7)
                )
                
                logger.info(f"Reminder sent for quote {quote.quote_number}")
                return {'success': True, 'message': 'Reminder sent'}
            
        except Exception as e:
            logger.error(f"Failed to send reminder: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _generate_access_token(self, quote):
        """Generate secure access token for client portal access."""
        import hashlib
        base_string = f"{quote.id}-{quote.client.email}-{timezone.now().isoformat()}"
        return hashlib.sha256(base_string.encode()).hexdigest()[:32]
    
    def _build_preview_url(self, quote, access_token, request=None):
        """Build secure URL for client to preview quote."""
        if request:
            base_url = request.build_absolute_uri('/')
        else:
            base_url = getattr(settings, 'SITE_URL', 'https://yourdomain.com/')
        
        return f"{base_url}quotes/{quote.id}/preview/{access_token}/"
    
    def _build_accept_url(self, quote, access_token, request=None):
        """Build secure URL for client to accept quote."""
        if request:
            base_url = request.build_absolute_uri('/')
        else:
            base_url = getattr(settings, 'SITE_URL', 'https://yourdomain.com/')
        
        return f"{base_url}quotes/{quote.id}/accept/{access_token}/"
    
    def _generate_quote_pdf(self, quote, request=None):
        """Generate PDF attachment for email."""
        try:
            from .views import generate_quote_pdf_buffer
            if request:
                return generate_quote_pdf_buffer(quote, request)
            else:
                # Create minimal request-like object for PDF generation
                class MockRequest:
                    def build_absolute_uri(self, path=''):
                        return getattr(settings, 'SITE_URL', 'https://yourdomain.com/') + path.lstrip('/')
                
                mock_request = MockRequest()
                return generate_quote_pdf_buffer(quote, mock_request)
        except Exception as e:
            logger.error(f"Failed to generate PDF for quote {quote.quote_number}: {str(e)}")
            return None
    
    def _update_quote_after_send(self, quote, access_token):
        """Update quote status and tracking after successful email send."""
        quote.status = 'sent'
        quote.sent_date = timezone.now()
        quote.save()
        
        # Store access token for client portal access
        quote.access_token = access_token
        quote.save(update_fields=['access_token'])
        
        # Create CRM interaction
        from crm.models import CustomerInteraction
        CustomerInteraction.objects.create(
            client=quote.client,
            interaction_type='quote_sent',
            subject=f'Quote {quote.quote_number} sent via email',
            notes=f'Quote emailed to {quote.client.email} with secure access link',
            next_followup=timezone.now() + timezone.timedelta(days=3),
            created_by=quote.created_by
        )
    
    def _get_company_info(self):
        """Get company information for email branding."""
        return {
            'name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
            'address': getattr(settings, 'COMPANY_ADDRESS', 'Harare, Zimbabwe'),
            'phone': getattr(settings, 'COMPANY_PHONE', '+263 XX XXX XXXX'),
            'email': getattr(settings, 'COMPANY_EMAIL', 'info@blitztech.co.zw'),
            'website': getattr(settings, 'COMPANY_WEBSITE', 'www.blitztech.co.zw'),
        }
    
    def _get_from_email(self):
        """Get the sender email address."""
        return getattr(settings, 'DEFAULT_FROM_EMAIL', 'quotes@blitztech.co.zw')
    
    def _get_cc_emails(self, quote):
        """Get CC recipients for quote emails."""
        cc_emails = []
        
        # Add assigned user if different from creator
        if quote.assigned_to and quote.assigned_to != quote.created_by:
            if quote.assigned_to.email:
                cc_emails.append(quote.assigned_to.email)
        
        # Add creator if they have an email
        if quote.created_by and quote.created_by.email:
            cc_emails.append(quote.created_by.email)
        
        # Add management for high-value quotes
        if quote.total_amount >= 10000:
            management_emails = getattr(settings, 'MANAGEMENT_CC_EMAILS', [])
            cc_emails.extend(management_emails)
        
        return list(set(cc_emails))  # Remove duplicates
    
    def _get_status_notification_recipients(self, quote, status_change):
        """Determine who should receive status change notifications."""
        recipients = []
        
        # Always notify the assigned user
        if quote.assigned_to and quote.assigned_to.email:
            recipients.append(quote.assigned_to.email)
        
        # Notify creator if different from assigned user
        if quote.created_by and quote.created_by.email and quote.created_by != quote.assigned_to:
            recipients.append(quote.created_by.email)
        
        # Notify management for important status changes
        important_statuses = ['accepted', 'rejected', 'expired']
        if status_change['new_status'] in important_statuses:
            management_emails = getattr(settings, 'MANAGEMENT_NOTIFICATION_EMAILS', [])
            recipients.extend(management_emails)
        
        return list(set(recipients))


# Email template helper functions
def send_quote_email(quote, request=None, custom_message=None):
    """Convenience function to send quote email."""
    service = QuoteEmailService()
    return service.send_quote_to_client(quote, request, custom_message)

def send_quote_notification(quote, status_change):
    """Convenience function to send status notifications."""
    service = QuoteEmailService()
    return service.send_quote_status_notification(quote, status_change)

def send_quote_reminder(quote, reminder_type='follow_up'):
    """Convenience function to send reminders."""
    service = QuoteEmailService()
    return service.send_quote_reminder(quote, reminder_type)
