from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    class Meta:
        model = AuditLog
        fields = [
            'id', 'username', 'action', 'description', 'object_type',
            'object_id', 'timestamp', 'ip_address', 'user_agent', 'extra_data',
        ]
