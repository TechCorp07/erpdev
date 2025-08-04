"""
URL configuration for blitzhub project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core.api import AuditLogViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    
    # Public website (homepage, about, services, etc.)
    path('', include('website.urls')),
    
    # Core authentication system (handles all user auth)
    path('auth/', include('core.urls')),
    
    # Business applications (employee access only)
    path('crm/', include('crm.urls')),
    path('inventory/', include('inventory.urls')),
    path('quotes/', include('quotes.urls')),
    
    # Customer-facing applications
    #path('shop/', include('shop.urls')),
    
    # Add any other URLs as apps are developed
    # path('hr/', include('hr.urls')),
    # path('blog/', include('blog.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler404 = 'website.views.handler404'
handler500 = 'website.views.handler500'