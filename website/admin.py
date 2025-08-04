from django.contrib import admin
from .models import (
    Category, BlogPost, Service, PortfolioItem, FAQ, 
    Contact, Testimonial, TeamMember, Partner, CompanyInfo
)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at', 'updated_at', 'is_published')
    list_filter = ('is_published', 'categories', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    filter_horizontal = ('categories',)
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'content')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Categories', {
            'fields': ('categories',)
        }),
        ('Publication', {
            'fields': ('is_published',)
        }),
    )

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'icon', 'order')
    list_filter = ('category',)
    list_editable = ('category', 'order')
    search_fields = ('title', 'description')

@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'date_completed', 'featured', 'order')
    list_filter = ('featured', 'type', 'categories', 'date_completed')
    list_editable = ('type', 'featured', 'order')
    search_fields = ('title', 'description', 'client')
    filter_horizontal = ('categories',)
    date_hierarchy = 'date_completed'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'client')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Categories and Display', {
            'fields': ('categories', 'type', 'url', 'date_completed', 'featured', 'order')
        }),
    )

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'order')
    list_filter = ('category',)
    list_editable = ('category', 'order')
    search_fields = ('question', 'answer')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'rating', 'is_active', 'order')
    list_filter = ('rating', 'is_active')
    list_editable = ('is_active', 'order')
    search_fields = ('name', 'position', 'company', 'content')

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'is_active', 'order')
    list_filter = ('is_active',)
    list_editable = ('is_active', 'order')
    search_fields = ('name', 'position', 'bio')

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',)
    search_fields = ('name',)

@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'website')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'address', 'phone', 'email', 'website')
        }),
        ('Social Media', {
            'fields': ('facebook', 'twitter', 'linkedin', 'instagram', 'youtube')
        }),
        ('Content', {
            'fields': ('mission', 'vision', 'about_us')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow adding if no instance exists
        return not CompanyInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the only instance
        return False
