import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from core.decorators import website_permission_required
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse

from .models import (
    BlogPost, Service, PortfolioItem, FAQ, 
    Contact, Testimonial, TeamMember, Partner, Category, CompanyInfo
)
from .forms import (
    BlogPostForm, ContactForm, NewsletterForm, SearchForm,
    CategoryForm, ServiceForm, PortfolioItemForm, FAQForm,
    TestimonialForm, TeamMemberForm, PartnerForm, CompanyInfoForm
)


def home(request):
    """View for the home page"""
    # Get main services with their specific categories
    services = Service.objects.all()[:6]  # Get first 6 services
    
    # For specialized service sections
    drone_services = Service.objects.filter(category='drone')[:3]
    iot_services = Service.objects.filter(category='iot')[:3]
    power_services = Service.objects.filter(category='power')[:3]
    research_services = Service.objects.filter(category='research')[:3]
    
    portfolio_items = PortfolioItem.objects.filter(featured=True)[:3]  # Featured projects
    testimonials = Testimonial.objects.filter(is_active=True)[:3]  # Active testimonials
    latest_posts = BlogPost.objects.filter(is_published=True)[:3]  # Latest blog posts
    partners = Partner.objects.all()
    
    # Company stats for counter section
    company_stats = {
        'projects_completed': '250+',
        'happy_clients': '100+', 
        'team_members': '25+',
        'years_experience': '5+'
    }
    
    context = {
        'services': services,
        'drone_services': drone_services,
        'iot_services': iot_services,
        'power_services': power_services,
        'research_services': research_services,
        'portfolio_items': portfolio_items,
        'testimonials': testimonials,
        'latest_posts': latest_posts,
        'partners': partners,
        'company_stats': company_stats,
    }
    return render(request, 'website/index.html', context)


def about(request):
    """View for about page"""
    team_members = TeamMember.objects.filter(is_active=True)
    
    # Company mission and vision content
    company_info = {
        'vision': 'Elevation of our clients\' business and lives through the power of custom-fit solutions',
        'mission': 'To become the leading innovative electronic systems developers in Zimbabwe by exceeding customers\' quality expectations through delivery of transcendent, tailor-made services of unstinting high quality and value addition.',
        'founding_year': '2017',
        'employees_count': '25+',
        'clients_served': '100+',
        'projects_completed': '250+'
    }
    
    # Core values
    core_values = [
        {
            'name': 'Resilience',
            'icon': 'award',
            'description': 'We adapt to changing needs and environments to ensure that our service quality maintains its high standards and meets your expectations at all times.'
        },
        {
            'name': 'Customer Commitment',
            'icon': 'people',
            'description': 'We foster lasting, professional relationships that make indelible improvements to our customers\' lives and businesses.'
        },
        {
            'name': 'Professionalism',
            'icon': 'briefcase',
            'description': 'We foster lasting, professional relationships that make indelible improvements to our customers\' lives and businesses.'
        },
        {
            'name': 'Integrity',
            'icon': 'shield-check',
            'description': 'We uphold the highest standards of integrity in all our actions and projects.'
        },
        {
            'name': 'Innovation',
            'icon': 'lightbulb',
            'description': 'Listening to each client allows us to adopt new, unique perspectives through which to explore, create and adapt new technology that works, every time.'
        }
    ]
    
    context = {
        'team_members': team_members,
        'company_info': company_info,
        'core_values': core_values,
        'motto': 'Transcend to the future.'
    }
    return render(request, 'website/about.html', context)


def services(request):
    """View for services page"""
    services_list = Service.objects.all()
    
    # Specific service categories for dedicated sections
    electronic_components = Service.objects.filter(category='components')
    software_development = Service.objects.filter(category='software')
    security_systems = Service.objects.filter(category='security')
    drone_technology = Service.objects.filter(category='drone')
    power_systems = Service.objects.filter(category='power')
    iot_systems = Service.objects.filter(category='iot')
    research_development = Service.objects.filter(category='research')
    pcb_fabrication = Service.objects.filter(category='pcb')
    
    context = {
        'services': services_list,
        'electronic_components': electronic_components,
        'software_development': software_development,
        'security_systems': security_systems,
        'drone_technology': drone_technology,
        'power_systems': power_systems,
        'iot_systems': iot_systems,
        'research_development': research_development,
        'pcb_fabrication': pcb_fabrication,
    }
    return render(request, 'website/services.html', context)


def portfolio(request):
    """View for portfolio page"""
    portfolio_items = PortfolioItem.objects.all()
    categories = Category.objects.filter(portfolio_items__isnull=False).distinct()
    
    # Filter by category if specified
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        portfolio_items = portfolio_items.filter(categories=category)
    
    # Filter by specific portfolio type if specified
    portfolio_type = request.GET.get('type')
    if portfolio_type:
        portfolio_items = portfolio_items.filter(type=portfolio_type)
    
    # Get client testimonials for the portfolio page
    testimonials = Testimonial.objects.filter(is_active=True)[:3]
    
    context = {
        'items': portfolio_items,
        'categories': categories,
        'current_category': category_slug,
        'testimonials': testimonials,
    }
    return render(request, 'website/portfolio.html', context)


def portfolio_detail(request, pk):
    """View for individual portfolio item"""
    item = get_object_or_404(PortfolioItem, pk=pk)
    related_items = PortfolioItem.objects.filter(
        categories__in=item.categories.all()
    ).exclude(pk=item.pk).distinct()[:3]
    
    context = {
        'item': item,
        'related_items': related_items,
    }
    return render(request, 'website/portfolio-detail.html', context)


def blog(request):
    """View for blog page"""
    posts = BlogPost.objects.filter(is_published=True)
    categories = Category.objects.filter(blog_posts__isnull=False).distinct()
    
    # Filter by category if specified
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(categories=category)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(posts, 6)  # Show 6 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'posts': page_obj,
        'categories': categories,
        'current_category': category_slug,
        'search_query': search_query,
    }
    return render(request, 'website/blog.html', context)


def blog_detail(request, slug):
    """View for individual blog post"""
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    recent_posts = BlogPost.objects.filter(is_published=True).exclude(pk=post.pk)[:5]
    related_posts = BlogPost.objects.filter(
        categories__in=post.categories.all()
    ).exclude(pk=post.pk).distinct()[:3]
    
    context = {
        'post': post,
        'recent_posts': recent_posts,
        'related_posts': related_posts,
    }
    return render(request, 'website/blog-detail.html', context)


def contact(request):
    """View for contact page"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            
            # Send email notification (optional)
            try:
                send_mail(
                    f"New Contact Form Submission: {form.cleaned_data['subject']}",
                    f"Name: {form.cleaned_data['name']}\nEmail: {form.cleaned_data['email']}\n\nMessage:\n{form.cleaned_data['message']}",
                    form.cleaned_data['email'],
                    ['sales@blitztechelectronics.co.zw'],
                    fail_silently=False,
                )
            except Exception as e:
                # Log the error but don't break the user experience
                pass
            
            messages.success(request, 'Your message has been sent successfully. We will contact you soon!')
            return redirect('website:contact')
    else:
        form = ContactForm()
    
    # Company contact information
    contact_info = {
        'address': '904 Premium Close, Mount Pleasant, Business Park, Harare, Zimbabwe',
        'email': 'sales@blitztechelectronics.co.zw',
        'phone': '+263 774 613 020',
        'office_hours': {
            'weekdays': '8:00 AM - 5:00 PM',
            'saturday': '9:00 AM - 1:00 PM',
            'sunday': 'Closed'
        }
    }
    
    # Common FAQs for the contact page
    contact_faqs = FAQ.objects.filter(category='contact')[:3]
    
    context = {
        'form': form,
        'contact_info': contact_info,
        'contact_faqs': contact_faqs,
    }
    return render(request, 'website/contact.html', context)


def faq(request):
    """View for FAQ page"""
    faqs = FAQ.objects.all()
    
    # Group FAQs by category
    components_faqs = FAQ.objects.filter(category='components')
    security_faqs = FAQ.objects.filter(category='security')
    iot_faqs = FAQ.objects.filter(category='iot')
    pcb_faqs = FAQ.objects.filter(category='pcb')
    power_faqs = FAQ.objects.filter(category='power')
    payment_faqs = FAQ.objects.filter(category='payment')
    
    # Define category information for visual display
    faq_categories = [
        {
            'id': 'components',
            'name': 'Components & Supply',
            'icon': 'cpu',
            'description': 'Questions about our electronic components, availability, and ordering process.'
        },
        {
            'id': 'security',
            'name': 'Security Systems',
            'icon': 'shield-lock',
            'description': 'Questions about security system installation, maintenance, and features.'
        },
        {
            'id': 'iot',
            'name': 'IoT & Smart Solutions',
            'icon': 'hdd-network',
            'description': 'Questions about our IoT systems, smart devices, and connectivity options.'
        },
        {
            'id': 'pcb',
            'name': 'PCB Fabrication',
            'icon': 'motherboard',
            'description': 'Questions about our PCB design, fabrication process, and specifications.'
        },
        {
            'id': 'power',
            'name': 'Power Systems',
            'icon': 'sun',
            'description': 'Questions about solar installations, electrical systems, and energy solutions.'
        },
        {
            'id': 'payment',
            'name': 'Orders & Payment',
            'icon': 'credit-card',
            'description': 'Questions about ordering process, payment options, and delivery.'
        }
    ]
    
    # Company contact information for the "Still Have Questions" section
    contact_info = {
        'phone': '+263 774 613 020',
        'email': 'sales@blitztechelectronics.co.zw'
    }
    
    context = {
        'faqs': faqs,
        'components_faqs': components_faqs,
        'security_faqs': security_faqs,
        'iot_faqs': iot_faqs,
        'pcb_faqs': pcb_faqs,
        'power_faqs': power_faqs,
        'payment_faqs': payment_faqs,
        'faq_categories': faq_categories,
        'contact_info': contact_info,
    }
    return render(request, 'website/faq.html', context)


def newsletter_signup(request):
    """View for newsletter signup (AJAX)"""
    if request.method == 'POST':
        form = NewsletterForm(request.POST)
        if form.is_valid():
            # In a real implementation, you would save this to a model or send to an email service
            # Here we'll just return a success message
            return JsonResponse({'success': True, 'message': 'Thank you for subscribing to our newsletter!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def search(request):
    """View for site-wide search"""
    search_query = request.GET.get('query', '')
    form = SearchForm(initial={'query': search_query})
    
    blog_results = []
    portfolio_results = []
    service_results = []
    faq_results = []
    
    if search_query:
        # Search in blog posts
        blog_results = BlogPost.objects.filter(
            Q(title__icontains=search_query) | 
            Q(content__icontains=search_query),
            is_published=True
        )
        
        # Search in portfolio items
        portfolio_results = PortfolioItem.objects.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
        
        # Search in services
        service_results = Service.objects.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
        
        # Search in FAQs
        faq_results = FAQ.objects.filter(
            Q(question__icontains=search_query) | 
            Q(answer__icontains=search_query)
        )
    
    context = {
        'form': form,
        'search_query': search_query,
        'blog_results': blog_results,
        'portfolio_results': portfolio_results,
        'service_results': service_results,
        'faq_results': faq_results,
        'total_results': len(blog_results) + len(portfolio_results) + len(service_results) + len(faq_results)
    }
    return render(request, 'website/search.html', context)

# =============================================================================
# BLOG MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('view')
def admin_dashboard(request):
    """Admin dashboard with ERP side panel integration"""
    stats = get_dashboard_stats(request)
    
    # Recent activity
    recent_posts = BlogPost.objects.order_by('-created_at')[:5]
    recent_contacts = Contact.objects.order_by('-created_at')[:5]
    recent_portfolio = PortfolioItem.objects.order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'recent_posts': recent_posts,
        'recent_contacts': recent_contacts,
        'recent_portfolio': recent_portfolio,
    }
    return render(request, 'website/admin_dashboard.html', context)

@website_permission_required('edit')
def manage_blog(request):
    posts = BlogPost.objects.order_by('-created_at')
    return render(request, 'website/blog/manage_blog.html', {'posts': posts})

@website_permission_required('edit')
def add_blog(request):
    if request.method == "POST":
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            blog = form.save(commit=False)
            blog.author = request.user
            blog.save()
            form.save_m2m()
            messages.success(request, 'Blog post created successfully!')
            return redirect('website:manage_blog')
    else:
        form = BlogPostForm()
    return render(request, 'website/blog/blog_form.html', {'form': form, 'title': "Add Blog Post"})

@website_permission_required('edit')
def edit_blog(request, pk):
    post = BlogPost.objects.get(pk=pk)
    if request.method == "POST":
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Blog post updated successfully!')
            return redirect('website:manage_blog')
    else:
        form = BlogPostForm(instance=post)
    return render(request, 'website/blog/blog_form.html', {'form': form, 'title': "Edit Blog Post"})

@website_permission_required('admin')
def delete_blog(request, pk):
    post = BlogPost.objects.get(pk=pk)
    if request.method == "POST":
        post.delete()
        messages.success(request, 'Blog post deleted successfully!')
        return redirect('website:manage_blog')
    return render(request, 'website/blog/confirm_delete.html', {'object': post, 'type': 'Blog Post'})

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

@website_permission_required('admin')
def get_dashboard_stats(request):
    """Get complete statistics for the website admin dashboard"""
    stats = {
        # Blog Statistics
        'total_blog_posts': BlogPost.objects.count(),
        'published_posts': BlogPost.objects.filter(is_published=True).count(),
        
        # Service Statistics  
        'total_services': Service.objects.count(),
        
        # Portfolio Statistics
        'total_portfolio': PortfolioItem.objects.count(),
        'featured_portfolio': PortfolioItem.objects.filter(featured=True).count(),
        
        # FAQ Statistics
        'total_faqs': FAQ.objects.count(),
        
        # Testimonial Statistics
        'total_testimonials': Testimonial.objects.count(),
        'active_testimonials': Testimonial.objects.filter(is_active=True).count(),
        
        # Team Statistics
        'total_team_members': TeamMember.objects.count(),
        'active_team_members': TeamMember.objects.filter(is_active=True).count(),
        
        # Partner Statistics
        'total_partners': Partner.objects.count(),
        
        # Contact Statistics
        'unread_contacts': Contact.objects.filter(is_read=False).count(),
        'total_contacts': Contact.objects.count(),
        
        # Category Statistics
        'total_categories': Category.objects.count(),
    }
    return stats

# =============================================================================
# CATEGORY MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_categories(request):
    """View to list all categories"""
    categories = Category.objects.order_by('name')
    context = {'categories': categories}
    return render(request, 'website/categories/manage_categories.html', context)

@website_permission_required('edit')
def add_category(request):
    """View to add a new category"""
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully!')
            return redirect('website:manage_categories')
    else:
        form = CategoryForm()
    
    context = {'form': form, 'title': "Add Category"}
    return render(request, 'website/categories/category_form.html', context)

@website_permission_required('edit')
def edit_category(request, pk):
    """View to edit an existing category"""
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('website:manage_categories')
    else:
        form = CategoryForm(instance=category)
    
    context = {'form': form, 'title': "Edit Category", 'object': category}
    return render(request, 'website/categories/category_form.html', context)

@website_permission_required('admin')
def delete_category(request, pk):
    """View to delete a category"""
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, 'Category deleted successfully!')
        return redirect('website:manage_categories')
    return render(request, 'website/categories/confirm_delete.html', {'object': category, 'type': 'Category'})

# =============================================================================
# SERVICE MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_services(request):
    """View to list all services"""
    services = Service.objects.order_by('category', 'order')
    context = {'services': services}
    return render(request, 'website/services/manage_services.html', context)

@website_permission_required('edit')
def add_service(request):
    """View to add a new service"""
    if request.method == "POST":
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service added successfully!')
            return redirect('website:manage_services')
    else:
        form = ServiceForm()
    
    context = {'form': form, 'title': "Add Service"}
    return render(request, 'website/services/service_form.html', context)

@website_permission_required('edit')
def edit_service(request, pk):
    """View to edit an existing service"""
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated successfully!')
            return redirect('website:manage_services')
    else:
        form = ServiceForm(instance=service)
    
    context = {'form': form, 'title': "Edit Service", 'object': service}
    return render(request, 'website/services/service_form.html', context)

@website_permission_required('admin')
def delete_service(request, pk):
    """View to delete a service"""
    service = get_object_or_404(Service, pk=pk)
    if request.method == "POST":
        service.delete()
        messages.success(request, 'Service deleted successfully!')
        return redirect('website:manage_services')
    
    context = {'object': service, 'type': 'Service'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# PORTFOLIO MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_portfolio(request):
    """View to list all portfolio items"""
    portfolio_items = PortfolioItem.objects.order_by('-featured', 'order', '-date_completed')
    context = {'portfolio_items': portfolio_items}
    return render(request, 'website/portfolio/manage_portfolio.html', context)

@website_permission_required('edit')
def add_portfolio(request):
    """View to add a new portfolio item"""
    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Portfolio item added successfully!')
            return redirect('website:manage_portfolio')
    else:
        form = PortfolioItemForm()
    
    context = {'form': form, 'title': "Add Portfolio Item"}
    return render(request, 'website/portfolio/portfolio_form.html', context)

@website_permission_required('edit')
def edit_portfolio(request, pk):
    """View to edit an existing portfolio item"""
    portfolio_item = get_object_or_404(PortfolioItem, pk=pk)
    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES, instance=portfolio_item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Portfolio item updated successfully!')
            return redirect('website:manage_portfolio')
    else:
        form = PortfolioItemForm(instance=portfolio_item)
    
    context = {'form': form, 'title': "Edit Portfolio Item", 'object': portfolio_item}
    return render(request, 'website/portfolio/portfolio_form.html', context)

@website_permission_required('admin')
def delete_portfolio(request, pk):
    """View to delete a portfolio item"""
    portfolio_item = get_object_or_404(PortfolioItem, pk=pk)
    if request.method == "POST":
        portfolio_item.delete()
        messages.success(request, 'Portfolio item deleted successfully!')
        return redirect('website:manage_portfolio')
    
    context = {'object': portfolio_item, 'type': 'Portfolio Item'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# FAQ MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_faqs(request):
    """View to list all FAQs"""
    faqs = FAQ.objects.order_by('category', 'order')
    context = {'faqs': faqs}
    return render(request, 'website/faqs/manage_faqs.html', context)

@website_permission_required('edit')
def add_faq(request):
    """View to add a new FAQ"""
    if request.method == "POST":
        form = FAQForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'FAQ added successfully!')
            return redirect('website:manage_faqs')
    else:
        form = FAQForm()
    
    context = {'form': form, 'title': "Add FAQ"}
    return render(request, 'website/faqs/faq_form.html', context)

@website_permission_required('edit')
def edit_faq(request, pk):
    """View to edit an existing FAQ"""
    faq = get_object_or_404(FAQ, pk=pk)
    if request.method == "POST":
        form = FAQForm(request.POST, instance=faq)
        if form.is_valid():
            form.save()
            messages.success(request, 'FAQ updated successfully!')
            return redirect('website:manage_faqs')
    else:
        form = FAQForm(instance=faq)
    
    context = {'form': form, 'title': "Edit FAQ", 'object': faq}
    return render(request, 'website/faqs/faq_form.html', context)

@website_permission_required('admin')
def delete_faq(request, pk):
    """View to delete a FAQ"""
    faq = get_object_or_404(FAQ, pk=pk)
    if request.method == "POST":
        faq.delete()
        messages.success(request, 'FAQ deleted successfully!')
        return redirect('website:manage_faqs')
    
    context = {'object': faq, 'type': 'FAQ'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# TESTIMONIAL MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_testimonials(request):
    """View to list all testimonials"""
    testimonials = Testimonial.objects.order_by('order')
    context = {'testimonials': testimonials}
    return render(request, 'website/testimonials/manage_testimonials.html', context)

@website_permission_required('edit')
def add_testimonial(request):
    """View to add a new testimonial"""
    if request.method == "POST":
        form = TestimonialForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Testimonial added successfully!')
            return redirect('website:manage_testimonials')
    else:
        form = TestimonialForm()
    
    context = {'form': form, 'title': "Add Testimonial"}
    return render(request, 'website/testimonials/testimonial_form.html', context)

@website_permission_required('edit')
def edit_testimonial(request, pk):
    """View to edit an existing testimonial"""
    testimonial = get_object_or_404(Testimonial, pk=pk)
    if request.method == "POST":
        form = TestimonialForm(request.POST, request.FILES, instance=testimonial)
        if form.is_valid():
            form.save()
            messages.success(request, 'Testimonial updated successfully!')
            return redirect('website:manage_testimonials')
    else:
        form = TestimonialForm(instance=testimonial)
    
    context = {'form': form, 'title': "Edit Testimonial", 'object': testimonial}
    return render(request, 'website/testimonials/testimonial_form.html', context)

@website_permission_required('admin')
def delete_testimonial(request, pk):
    """View to delete a testimonial"""
    testimonial = get_object_or_404(Testimonial, pk=pk)
    if request.method == "POST":
        testimonial.delete()
        messages.success(request, 'Testimonial deleted successfully!')
        return redirect('website:manage_testimonials')
    
    context = {'object': testimonial, 'type': 'Testimonial'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# TEAM MEMBER MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_team(request):
    """View to list all team members"""
    team_members = TeamMember.objects.order_by('order')
    context = {'team_members': team_members}
    return render(request, 'website/team/manage_team.html', context)

@website_permission_required('edit')
def add_team_member(request):
    """View to add a new team member"""
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Team member added successfully!')
            return redirect('website:manage_team')
    else:
        form = TeamMemberForm()
    
    context = {'form': form, 'title': "Add Team Member"}
    return render(request, 'website/team/team_form.html', context)

@website_permission_required('edit')
def edit_team_member(request, pk):
    """View to edit an existing team member"""
    team_member = get_object_or_404(TeamMember, pk=pk)
    if request.method == "POST":
        form = TeamMemberForm(request.POST, request.FILES, instance=team_member)
        if form.is_valid():
            form.save()
            messages.success(request, 'Team member updated successfully!')
            return redirect('website:manage_team')
    else:
        form = TeamMemberForm(instance=team_member)
    
    context = {'form': form, 'title': "Edit Team Member", 'object': team_member}
    return render(request, 'website/team/team_form.html', context)

@website_permission_required('admin')
def delete_team_member(request, pk):
    """View to delete a team member"""
    team_member = get_object_or_404(TeamMember, pk=pk)
    if request.method == "POST":
        team_member.delete()
        messages.success(request, 'Team member deleted successfully!')
        return redirect('website:manage_team')
    
    context = {'object': team_member, 'type': 'Team Member'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# PARTNER MANAGEMENT VIEWS
# =============================================================================

@website_permission_required('edit')
def manage_partners(request):
    """View to list all partners"""
    partners = Partner.objects.order_by('order')
    context = {'partners': partners}
    return render(request, 'website/partners/manage_partners.html', context)

@website_permission_required('edit')
def add_partner(request):
    """View to add a new partner"""
    if request.method == "POST":
        form = PartnerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Partner added successfully!')
            return redirect('website:manage_partners')
    else:
        form = PartnerForm()
    
    context = {'form': form, 'title': "Add Partner"}
    return render(request, 'website/partners/partner_form.html', context)

@website_permission_required('edit')
def edit_partner(request, pk):
    """View to edit an existing partner"""
    partner = get_object_or_404(Partner, pk=pk)
    if request.method == "POST":
        form = PartnerForm(request.POST, request.FILES, instance=partner)
        if form.is_valid():
            form.save()
            messages.success(request, 'Partner updated successfully!')
            return redirect('website:manage_partners')
    else:
        form = PartnerForm(instance=partner)
    
    context = {'form': form, 'title': "Edit Partner", 'object': partner}
    return render(request, 'website/partners/partner_form.html', context)

@website_permission_required('admin')
def delete_partner(request, pk):
    """View to delete a partner"""
    partner = get_object_or_404(Partner, pk=pk)
    if request.method == "POST":
        partner.delete()
        messages.success(request, 'Partner deleted successfully!')
        return redirect('website:manage_partners')
    
    context = {'object': partner, 'type': 'Partner'}
    return render(request, 'website/confirm_delete.html', context)

# =============================================================================
# COMPANY INFO MANAGEMENT VIEW
# =============================================================================
@website_permission_required('edit')
def manage_company_info(request):
    """View company information"""
    try:
        company_info = CompanyInfo.objects.get()
    except CompanyInfo.DoesNotExist:
        company_info = CompanyInfo.objects.create()
    
    context = {'company_info': company_info}
    return render(request, 'website/company/manage_company_info.html', context)

@website_permission_required('edit')
def edit_company_info(request):
    """View to edit company information"""
    # Get or create the company info instance
    try:
        company_info = CompanyInfo.objects.get()
    except CompanyInfo.DoesNotExist:
        company_info = CompanyInfo.objects.create()
    
    if request.method == "POST":
        form = CompanyInfoForm(request.POST, instance=company_info)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company information updated successfully!')
            return redirect('website:admin_dashboard')
    else:
        form = CompanyInfoForm(instance=company_info)
    
    context = {'form': form, 'title': "Edit Company Information", 'object': company_info}
    return render(request, 'website/company/company_form.html', context)

# =============================================================================
# CONTACT MANAGEMENT VIEWS (READ-ONLY)
# =============================================================================

@website_permission_required('view')
def manage_contacts(request):
    """View to list all contact form submissions"""
    contacts = Contact.objects.order_by('-created_at')
    
    # Add pagination for better performance
    paginator = Paginator(contacts, 20)  # Show 20 contacts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'contacts': page_obj}
    return render(request, 'website/contacts/manage_contacts.html', context)

@website_permission_required('view')
def view_contact(request, pk):
    """View to display a single contact form submission"""
    contact = get_object_or_404(Contact, pk=pk)
    
    # Mark as read when viewed
    if not contact.is_read:
        contact.is_read = True
        contact.save()
    
    context = {'contact': contact}
    return render(request, 'website/contacts/view_contact.html', context)

# =============================================================================
# AJAX VIEWS (Optional for enhanced UX)
# =============================================================================

@website_permission_required('edit')
def toggle_blog_published(request, pk):
    """Toggle blog post published status via AJAX"""
    if request.method == 'POST':
        post = get_object_or_404(BlogPost, pk=pk)
        post.is_published = not post.is_published
        post.save()
        return JsonResponse({
            'success': True,
            'is_published': post.is_published,
            'message': f'Post {"published" if post.is_published else "unpublished"} successfully'
        })
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@website_permission_required('edit')
def toggle_testimonial_active(request, pk):
    """Toggle testimonial active status via AJAX"""
    if request.method == 'POST':
        testimonial = get_object_or_404(Testimonial, pk=pk)
        testimonial.is_active = not testimonial.is_active
        testimonial.save()
        
        return JsonResponse({
            'success': True,
            'is_active': testimonial.is_active,
            'status': 'Active' if testimonial.is_active else 'Inactive'
        })
    return JsonResponse({'success': False, 'status': 'Invalid request'})

@website_permission_required('edit')
def toggle_portfolio_featured(request, pk):
    """Toggle portfolio item featured status via AJAX"""
    if request.method == 'POST':
        item = get_object_or_404(PortfolioItem, pk=pk)
        item.featured = not item.featured
        item.save()
        
        return JsonResponse({
            'success': True,
            'featured': item.featured,
            'status': 'Featured' if item.featured else 'Unfeatured'
        })
    return JsonResponse({'success': False, 'status': 'Invalid request'})

@website_permission_required('view')
def mark_contact_read(request, pk):
    """Mark contact as read via AJAX"""
    if request.method == 'POST':
        contact = get_object_or_404(Contact, pk=pk)
        contact.is_read = True
        contact.save()
        
        return JsonResponse({
            'success': True,
            'is_read': True,
            'status': 'Read'
        })
    return JsonResponse({'success': False, 'status': 'Invalid request'})

# =============================================================================
# BULK OPERATIONS (Optional for efficiency)
# =============================================================================

@website_permission_required('admin')
def bulk_delete_contacts(request):
    """Delete multiple contacts at once"""
    if request.method == 'POST':
        contact_ids = request.POST.getlist('contact_ids')
        if contact_ids:
            Contact.objects.filter(id__in=contact_ids).delete()
            messages.success(request, f'Successfully deleted {len(contact_ids)} contacts')
        else:
            messages.warning(request, 'No contacts selected for deletion')
        return redirect('website:manage_contacts')
    
    return redirect('website:manage_contacts')

@website_permission_required('edit')
def bulk_publish_posts(request):
    """Publish multiple blog posts at once"""
    if request.method == 'POST':
        post_ids = request.POST.getlist('post_ids')
        if post_ids:
            BlogPost.objects.filter(id__in=post_ids).update(is_published=True)
            messages.success(request, f'Successfully published {len(post_ids)} posts')
        else:
            messages.warning(request, 'No posts selected for publishing')
        return redirect('website:manage_blog')
    
    return redirect('website:manage_blog')

# =============================================================================
# EXPORT FUNCTIONALITY (Optional)
# =============================================================================

@website_permission_required('admin')
def export_contacts_csv(request):
    """Export contacts to CSV file"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="website_contacts.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Subject', 'Message', 'Created', 'Read'])
    
    contacts = Contact.objects.all().order_by('-created_at')
    for contact in contacts:
        writer.writerow([
            contact.name,
            contact.email,
            contact.subject,
            contact.message,
            contact.created_at.strftime('%Y-%m-%d %H:%M'),
            'Yes' if contact.is_read else 'No'
        ])
    
    return response

@website_permission_required('admin')
def export_blog_posts_csv(request):
    """Export blog posts to CSV file"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="blog_posts.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Title', 'Author', 'Categories', 'Published', 'Created', 'Updated'])
    
    posts = BlogPost.objects.all().order_by('-created_at')
    for post in posts:
        categories = ', '.join([cat.name for cat in post.categories.all()])
        writer.writerow([
            post.title,
            post.author.get_full_name() or post.author.username,
            categories,
            'Yes' if post.is_published else 'No',
            post.created_at.strftime('%Y-%m-%d %H:%M'),
            post.updated_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    return response

def handler404(request, exception):
    """Custom 404 error page"""
    return render(request, 'website/404.html', status=404)


def handler500(request):
    """Custom 500 error page"""
    return render(request, 'website/500.html', status=500)