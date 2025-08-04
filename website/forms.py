from django import forms
from .models import (
    BlogPost, Category, Contact, Service, PortfolioItem, 
    FAQ, Testimonial, TeamMember, Partner, CompanyInfo
)


class ContactForm(forms.ModelForm):
    """Contact form that maps to the Contact model"""
    
    class Meta:
        model = Contact
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your Email'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Your Message', 'rows': 5}),
        }


class NewsletterForm(forms.Form):
    """Form for newsletter signup"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your Email Address'})
    )


class SearchForm(forms.Form):
    """Form for site-wide search"""
    
    query = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search...'})
    )


class BlogPostForm(forms.ModelForm):
    """Form for creating and editing blog posts"""
    
    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'image', 'categories', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'categories': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""
    
    class Meta:
        model = Category
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'URL slug (auto-generated if empty)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug field optional - it will be auto-generated if empty
        self.fields['slug'].required = False
        self.fields['slug'].help_text = "Leave empty to auto-generate from name"


class ServiceForm(forms.ModelForm):
    """Form for creating and editing services"""
    
    class Meta:
        model = Service
        fields = ['title', 'description', 'icon', 'category', 'image', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Service Description'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bootstrap icon name (e.g., code-slash)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['icon'].help_text = "Bootstrap icon name without 'bi-' prefix (e.g., 'code-slash', 'shield-lock')"
        self.fields['order'].help_text = "Lower numbers appear first"


class PortfolioItemForm(forms.ModelForm):
    """Form for creating and editing portfolio items"""
    
    class Meta:
        model = PortfolioItem
        fields = ['title', 'description', 'image', 'categories', 'type', 'client', 'url', 'date_completed', 'featured', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Project Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Project Description'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'categories': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client Name (optional)'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Project URL (optional)'}),
            'date_completed': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].required = False
        self.fields['url'].required = False
        self.fields['date_completed'].required = False
        self.fields['order'].help_text = "Lower numbers appear first"


class FAQForm(forms.ModelForm):
    """Form for creating and editing FAQs"""
    
    class Meta:
        model = FAQ
        fields = ['question', 'answer', 'category', 'order']
        widgets = {
            'question': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Frequently Asked Question'}),
            'answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Answer to the question'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['order'].help_text = "Lower numbers appear first within each category"


class TestimonialForm(forms.ModelForm):
    """Form for creating and editing testimonials"""
    
    class Meta:
        model = Testimonial
        fields = ['name', 'position', 'company', 'image', 'content', 'rating', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client Name'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Testimonial content'}),
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].required = False
        self.fields['order'].help_text = "Lower numbers appear first"


class TeamMemberForm(forms.ModelForm):
    """Form for creating and editing team members"""
    
    class Meta:
        model = TeamMember
        fields = ['name', 'position', 'bio', 'image', 'email', 'linkedin', 'twitter', 'github', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Brief biography'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'LinkedIn Profile URL'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Twitter Profile URL'}),
            'github': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'GitHub Profile URL'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make optional fields actually optional
        optional_fields = ['bio', 'email', 'linkedin', 'twitter', 'github']
        for field_name in optional_fields:
            self.fields[field_name].required = False
        
        self.fields['order'].help_text = "Lower numbers appear first"


class PartnerForm(forms.ModelForm):
    """Form for creating and editing partners"""
    
    class Meta:
        model = Partner
        fields = ['name', 'logo', 'url', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Partner/Client Name'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Partner Website URL (optional)'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Display order'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['url'].required = False
        self.fields['order'].help_text = "Lower numbers appear first"


class CompanyInfoForm(forms.ModelForm):
    """Form for editing company information"""
    
    class Meta:
        model = CompanyInfo
        fields = [
            'name', 'address', 'phone', 'email', 'website',
            'facebook', 'twitter', 'linkedin', 'instagram', 'youtube',
            'mission', 'vision', 'about_us'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Company Address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Contact Email'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Website URL'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Facebook Page URL'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Twitter Profile URL'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'LinkedIn Company Page URL'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Instagram Profile URL'}),
            'youtube': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'YouTube Channel URL'}),
            'mission': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Company Mission Statement'}),
            'vision': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Company Vision Statement'}),
            'about_us': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'About Us Content'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make social media and content fields optional
        optional_fields = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'mission', 'vision', 'about_us']
        for field_name in optional_fields:
            self.fields[field_name].required = False
