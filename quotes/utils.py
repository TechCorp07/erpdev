# quotes/utils.py
"""
Quote System Utility Functions

This module contains helper functions for PDF generation, pricing calculations,
email processing, and other utility operations used throughout the quote system.
"""

import os
import hashlib
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from io import BytesIO

from django.conf import settings
from django.template.loader import get_template, render_to_string
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse

import logging
logger = logging.getLogger(__name__)

# PDF Generation Utilities
try:
    from weasyprint import HTML, CSS
    from weasyprint.fonts import FontConfiguration
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("WeasyPrint not available. PDF generation will be disabled.")

def generate_quote_pdf_buffer(quote, request=None):
    """
    Generate PDF buffer for email attachments or downloads.
    
    Args:
        quote: Quote instance
        request: HTTP request object (optional)
    
    Returns:
        BytesIO buffer containing PDF data
    """
    if not PDF_AVAILABLE:
        raise ImportError("PDF generation requires WeasyPrint. Install with: pip install weasyprint")
    
    try:
        # Get quote items with related data
        quote_items = quote.items.all().select_related('product', 'supplier')
        
        # Prepare context for PDF template
        context = {
            'quote': quote,
            'quote_items': quote_items,
            'company_info': get_company_info(),
            'generated_date': timezone.now(),
            'generated_by': getattr(request, 'user', None),
            'pdf_settings': get_pdf_settings(),
        }
        
        # Render HTML template
        template = get_template('quotes/quote_pdf.html')
        html_content = template.render(context)
        
        # Configure fonts for professional appearance
        font_config = FontConfiguration()
        
        # Create PDF
        html_doc = HTML(string=html_content, base_url=get_base_url(request))
        pdf_buffer = BytesIO()
        
        # Apply custom CSS if available
        css_path = get_pdf_css_path()
        if css_path and os.path.exists(css_path):
            css = CSS(filename=css_path, font_config=font_config)
            html_doc.write_pdf(pdf_buffer, stylesheets=[css], font_config=font_config)
        else:
            html_doc.write_pdf(pdf_buffer, font_config=font_config)
        
        pdf_buffer.seek(0)
        return pdf_buffer
        
    except Exception as e:
        logger.error(f"Error generating PDF for quote {quote.quote_number}: {str(e)}")
        raise

def get_company_info():
    """Get company information for documents and emails"""
    return {
        'name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
        'address': getattr(settings, 'COMPANY_ADDRESS', 'Harare, Zimbabwe'),
        'phone': getattr(settings, 'COMPANY_PHONE', '+263 XX XXX XXXX'),
        'email': getattr(settings, 'COMPANY_EMAIL', 'info@blitztechelectronics.co.zw'),
        'website': getattr(settings, 'COMPANY_WEBSITE', 'www.blitztechelectronics.co.zw'),
        'logo_path': getattr(settings, 'COMPANY_LOGO_PATH', None),
        'tax_number': getattr(settings, 'COMPANY_TAX_NUMBER', None),
    }

def get_pdf_settings():
    """Get PDF-specific configuration settings"""
    return {
        'show_profit_analysis': getattr(settings, 'PDF_SHOW_PROFIT_ANALYSIS', False),
        'show_terms_and_conditions': getattr(settings, 'PDF_SHOW_TERMS', True),
        'watermark_text': getattr(settings, 'PDF_WATERMARK', None),
        'footer_text': getattr(settings, 'PDF_FOOTER_TEXT', 'Thank you for your business!'),
        'color_scheme': getattr(settings, 'PDF_COLOR_SCHEME', 'blue'),
    }

def get_pdf_css_path():
    """Get path to PDF CSS file"""
    static_dirs = getattr(settings, 'STATICFILES_DIRS', [])
    static_root = getattr(settings, 'STATIC_ROOT', None)
    
    # Try static root first (production)
    if static_root:
        css_path = os.path.join(static_root, 'quotes', 'css', 'quote_pdf.css')
        if os.path.exists(css_path):
            return css_path
    
    # Try static dirs (development)
    for static_dir in static_dirs:
        css_path = os.path.join(static_dir, 'quotes', 'css', 'quote_pdf.css')
        if os.path.exists(css_path):
            return css_path
    
    return None

def get_base_url(request=None):
    """Get base URL for absolute links in PDFs"""
    if request:
        return request.build_absolute_uri('/')
    return getattr(settings, 'SITE_URL', 'https://yourdomain.com/')

# Pricing Calculation Utilities

class PricingCalculator:
    """Advanced pricing calculation utilities"""
    
    def __init__(self):
        self.default_markup = Decimal('30.00')  # 30% default markup
        self.vat_rate = Decimal('15.00')  # Zimbabwe VAT rate
    
    def calculate_markup_price(self, cost_price, markup_percentage):
        """Calculate selling price with markup"""
        if not cost_price or cost_price <= 0:
            return Decimal('0.00')
        
        markup_decimal = Decimal(str(markup_percentage)) / 100
        selling_price = cost_price * (1 + markup_decimal)
        return self.round_currency(selling_price)
    
    def calculate_profit_margin(self, selling_price, cost_price):
        """Calculate profit margin percentage"""
        if not cost_price or cost_price <= 0:
            return Decimal('0.00')
        
        profit = selling_price - cost_price
        margin = (profit / cost_price) * 100
        return self.round_percentage(margin)
    
    def calculate_vat_inclusive(self, amount):
        """Calculate VAT-inclusive amount"""
        vat_amount = amount * self.vat_rate / 100
        return {
            'exclusive_amount': self.round_currency(amount),
            'vat_amount': self.round_currency(vat_amount),
            'inclusive_amount': self.round_currency(amount + vat_amount)
        }
    
    def suggest_pricing_tiers(self, cost_price):
        """Suggest multiple pricing tiers"""
        if not cost_price or cost_price <= 0:
            return []
        
        tiers = [
            ('economy', 20, 'Economy Pricing'),
            ('standard', 30, 'Standard Pricing'),
            ('premium', 50, 'Premium Pricing'),
            ('luxury', 100, 'Luxury Pricing')
        ]
        
        suggestions = []
        for tier_key, markup, tier_name in tiers:
            price = self.calculate_markup_price(cost_price, markup)
            margin = self.calculate_profit_margin(price, cost_price)
            
            suggestions.append({
                'tier': tier_key,
                'name': tier_name,
                'markup_percent': markup,
                'selling_price': price,
                'profit_margin': margin,
                'profit_amount': price - cost_price
            })
        
        return suggestions
    
    def round_currency(self, amount):
        """Round currency to 2 decimal places"""
        if amount is None:
            return Decimal('0.00')
        return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def round_percentage(self, percentage):
        """Round percentage to 2 decimal places"""
        if percentage is None:
            return Decimal('0.00')
        return Decimal(str(percentage)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Email Utilities

def send_professional_email(subject, template_name, context, to_email, 
                          from_email=None, cc_emails=None, attachments=None):
    """
    Send professional email with HTML/text templates and attachments
    
    Args:
        subject: Email subject line
        template_name: Base template name (without .html/.txt)
        context: Template context dictionary
        to_email: Recipient email address
        from_email: Sender email (optional)
        cc_emails: List of CC recipients (optional)
        attachments: List of attachment tuples (filename, content, mimetype)
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Render email templates
        html_template = f'quotes/emails/{template_name}.html'
        text_template = f'quotes/emails/{template_name}.txt'
        
        html_content = render_to_string(html_template, context)
        text_content = render_to_string(text_template, context)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            cc=cc_emails or []
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Add attachments if provided
        if attachments:
            for filename, content, mimetype in attachments:
                email.attach(filename, content, mimetype)
        
        # Send email
        result = email.send()
        
        if result:
            logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            logger.error(f"Failed to send email to {to_email}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {str(e)}")
        return False

# Security Utilities

def generate_secure_token(length=32):
    """Generate cryptographically secure random token"""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:length]

def verify_access_token(quote, provided_token):
    """Verify client access token for quote"""
    if not provided_token or len(provided_token) != 32:
        return False
    
    # Check stored token first
    if hasattr(quote, 'access_token') and quote.access_token:
        return quote.access_token == provided_token
    
    # Fallback to generated token for backward compatibility
    expected_token = generate_quote_access_token(quote)
    return expected_token == provided_token

def generate_quote_access_token(quote):
    """Generate access token for quote client portal"""
    base_string = f"{quote.id}-{quote.client.email}-{quote.created_at.isoformat()}"
    return hashlib.sha256(base_string.encode()).hexdigest()[:32]

# Data Export Utilities

def export_quotes_to_excel(quotes, filename=None):
    """Export quotes to Excel format"""
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        
        # Prepare data
        data = []
        for quote in quotes:
            data.append({
                'Quote Number': quote.quote_number,
                'Client': quote.client.name,
                'Company': quote.client.company or '',
                'Title': quote.title,
                'Status': quote.get_status_display(),
                'Total Amount': float(quote.total_amount),
                'Currency': quote.currency,
                'Created Date': quote.created_at.strftime('%Y-%m-%d'),
                'Valid Until': quote.validity_date.strftime('%Y-%m-%d'),
                'Assigned To': quote.assigned_to.get_full_name() if quote.assigned_to else '',
                'Items Count': quote.items.count()
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Quotes', index=False)
            
            # Style the worksheet
            worksheet = writer.sheets['Quotes']
            
            # Header styling
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        return output
        
    except ImportError:
        logger.error("pandas and openpyxl required for Excel export")
        raise ImportError("Install pandas and openpyxl for Excel export functionality")
    except Exception as e:
        logger.error(f"Error exporting quotes to Excel: {str(e)}")
        raise

# Validation Utilities

def validate_quote_data(quote_data):
    """Validate quote data before processing"""
    errors = []
    
    # Required fields
    required_fields = ['client', 'title', 'validity_date']
    for field in required_fields:
        if not quote_data.get(field):
            errors.append(f'{field.title()} is required')
    
    # Validity date must be in future
    validity_date = quote_data.get('validity_date')
    if validity_date and validity_date <= timezone.now().date():
        errors.append('Validity date must be in the future')
    
    # Discount percentage validation
    discount = quote_data.get('discount_percentage', 0)
    if discount < 0 or discount > 100:
        errors.append('Discount percentage must be between 0 and 100')
    
    # Tax rate validation
    tax_rate = quote_data.get('tax_rate', 0)
    if tax_rate < 0 or tax_rate > 100:
        errors.append('Tax rate must be between 0 and 100')
    
    return errors

# Currency Utilities

def format_currency(amount, currency='USD'):
    """Format currency for display"""
    if currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'ZWG':
        return f"ZWG {amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"

def convert_currency(amount, from_currency, to_currency, rate=None):
    """Convert between currencies"""
    if from_currency == to_currency:
        return amount
    
    if not rate:
        # In production, get from exchange rate API
        # For now, use fixed rates
        rates = {
            ('USD', 'ZWG'): Decimal('25.0'),
            ('ZWG', 'USD'): Decimal('0.04')
        }
        rate = rates.get((from_currency, to_currency), Decimal('1.0'))
    
    converted = amount * Decimal(str(rate))
    return PricingCalculator().round_currency(converted)

# File Utilities

def get_upload_path(instance, filename):
    """Generate upload path for quote attachments"""
    quote_id = getattr(instance, 'quote_id', 'unknown')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(filename)
    safe_filename = f"{name}_{timestamp}{ext}"
    return f"quotes/{quote_id}/attachments/{safe_filename}"

def validate_file_upload(uploaded_file):
    """Validate uploaded files"""
    # Maximum file size (10MB)
    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValueError("File size too large. Maximum 10MB allowed.")
    
    # Allowed file types
    allowed_types = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png']
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    if file_ext not in allowed_types:
        raise ValueError(f"File type {file_ext} not allowed.")
    
    return True
