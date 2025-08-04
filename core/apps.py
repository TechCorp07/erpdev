from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        This method is called when the application is ready.
        Import signals here to ensure they're registered.
        """
        import core.signals
