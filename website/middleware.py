"""
Custom middleware for the website app
"""
import time
from django.utils.deprecation import MiddlewareMixin

class ResponseTimeMiddleware(MiddlewareMixin):
    """
    Middleware to measure response time
    Useful for performance monitoring
    """
    
    def process_request(self, request):
        request._request_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, '_request_time'):
            response_time = time.time() - request._request_time
            response['X-Response-Time'] = str(int(response_time * 1000))  # in milliseconds
        return response