"""
Context processors for the website app
These will add data to the context of all templates
"""
from .models import Service, Category, CompanyInfo
from .forms import SearchForm, NewsletterForm

def website_context(request):
    """
    Add common website data to all templates
    """
    # Get company information
    try:
        company_info = CompanyInfo.objects.first()
    except:
        company_info = None
        
    # Services organized by category for navigation dropdown
    service_categories = {
        'components': Service.objects.filter(category='components')[:3],
        'software': Service.objects.filter(category='software')[:3],
        'security': Service.objects.filter(category='security')[:3],
        'drone': Service.objects.filter(category='drone')[:3],
        'power': Service.objects.filter(category='power')[:3],
        'iot': Service.objects.filter(category='iot')[:3],
        'research': Service.objects.filter(category='research')[:3],
        'pcb': Service.objects.filter(category='pcb')[:3],
    }
        
    return {
        'all_services': Service.objects.all()[:6],  # For basic nav dropdown
        'service_categories': service_categories,   # Categorized services
        'all_categories': Category.objects.all(),   # For blog and portfolio filters
        'search_form': SearchForm(),                # For search input in nav
        'newsletter_form': NewsletterForm(),        # For newsletter subscription
        'company_info': company_info,               # Company contact details
        
        # Company details as individual variables for easier template access
        'company_name': company_info.name if company_info else 'BlitzTech Electronics',
        'company_address': company_info.address if company_info else '904 Premium Close, Mount Pleasant, Business Park, Harare, Zimbabwe',
        'company_phone': company_info.phone if company_info else '+263 774 613 020',
        'company_email': company_info.email if company_info else 'sales@blitztechelectronics.co.zw',
        'company_website': company_info.website if company_info else 'www.blitztechelectronics.co.zw',
    }
