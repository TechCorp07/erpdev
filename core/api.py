from rest_framework import viewsets, permissions, filters
from .models import AuditLog
from .serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing/filtering audit logs.
    Only admins/managers can access.
    """
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'action', 'description', 'object_type', 'object_id', 'ip_address']
    ordering_fields = ['timestamp', 'action', 'user__username', 'object_type']
    ordering = ['-timestamp']
