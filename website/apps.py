from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'website'
    
    def ready(self):
        """
        This method is called when the application is ready.
        You can register any signals here.
        """
        pass