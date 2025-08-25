from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    
    # Portfolio
    path('portfolio/', views.portfolio, name='portfolio'),
    path('portfolio/<int:pk>/', views.portfolio_detail, name='portfolio_detail'),
    
    # Blog
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    
    # Contact and FAQ
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    
    # Newsletter
    path('newsletter-signup/', views.newsletter_signup, name='newsletter_signup'),
    
    # Search
    path('search/', views.search, name='search'),

    # Website Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Blog management
    path('manage/blog/', views.manage_blog, name='manage_blog'),
    path('manage/blog/add/', views.add_blog, name='add_blog'),
    path('manage/blog/<int:pk>/edit/', views.edit_blog, name='edit_blog'),
    path('manage/blog/<int:pk>/delete/', views.delete_blog, name='delete_blog'),
    
    # Categories
    path('manage/categories/', views.manage_categories, name='manage_categories'),
    path('manage/categories/add/', views.add_category, name='add_category'),
    path('manage/categories/<int:pk>/edit/', views.edit_category, name='edit_category'),
    path('manage/categories/<int:pk>/delete/', views.delete_category, name='delete_category'),

    # Services
    path('manage/services/', views.manage_services, name='manage_services'),
    path('manage/services/add/', views.add_service, name='add_service'),
    path('manage/services/<int:pk>/edit/', views.edit_service, name='edit_service'),
    path('manage/services/<int:pk>/delete/', views.delete_service, name='delete_service'),

    # Portfolio management
    path('manage/portfolio/', views.manage_portfolio, name='manage_portfolio'),
    path('manage/portfolio/add/', views.add_portfolio, name='add_portfolio'),
    path('manage/portfolio/<int:pk>/edit/', views.edit_portfolio, name='edit_portfolio'),
    path('manage/portfolio/<int:pk>/delete/', views.delete_portfolio, name='delete_portfolio'),

    # FAQs management
    path('manage/faqs/', views.manage_faqs, name='manage_faqs'),
    path('manage/faqs/add/', views.add_faq, name='add_faq'),
    path('manage/faqs/<int:pk>/edit/', views.edit_faq, name='edit_faq'),
    path('manage/faqs/<int:pk>/delete/', views.delete_faq, name='delete_faq'),

    # Testimonials management
    path('manage/testimonials/', views.manage_testimonials, name='manage_testimonials'),
    path('manage/testimonials/add/', views.add_testimonial, name='add_testimonial'),
    path('manage/testimonials/<int:pk>/edit/', views.edit_testimonial, name='edit_testimonial'),
    path('manage/testimonials/<int:pk>/delete/', views.delete_testimonial, name='delete_testimonial'),

    # Team management
    path('manage/team/', views.manage_team, name='manage_team'),
    path('manage/team/add/', views.add_team_member, name='add_team_member'),
    path('manage/team/<int:pk>/edit/', views.edit_team_member, name='edit_team_member'),
    path('manage/team/<int:pk>/delete/', views.delete_team_member, name='delete_team_member'),

    # Partners management
    path('manage/partners/', views.manage_partners, name='manage_partners'),
    path('manage/partners/add/', views.add_partner, name='add_partner'),
    path('manage/partners/<int:pk>/edit/', views.edit_partner, name='edit_partner'),
    path('manage/partners/<int:pk>/delete/', views.delete_partner, name='delete_partner'),

    # Company Info management
    path('manage/company-info/edit/', views.edit_company_info, name='edit_company_info'),

    # Contact management (read-only)
    path('manage/contacts/', views.manage_contacts, name='manage_contacts'),
    path('manage/contacts/<int:pk>/', views.view_contact, name='view_contact'),
    
    # Export URLs
    path('export/contacts.csv', views.export_contacts_csv, name='export_contacts_csv'),
    path('export/blog-posts.csv', views.export_blog_posts_csv, name='export_blog_posts_csv'),
    
    # AJAX toggle URLs (for quick status changes)
    path('ajax/blog/<int:pk>/toggle-published/', views.toggle_blog_published, name='toggle_blog_published'),
    path('ajax/testimonial/<int:pk>/toggle-active/', views.toggle_testimonial_active, name='toggle_testimonial_active'),
    path('ajax/portfolio/<int:pk>/toggle-featured/', views.toggle_portfolio_featured, name='toggle_portfolio_featured'),
    path('ajax/contact/<int:pk>/mark-read/', views.mark_contact_read, name='mark_contact_read'),    
]