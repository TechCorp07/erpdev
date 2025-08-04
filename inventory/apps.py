# inventory/apps.py - Inventory App Configuration

"""
Django App Configuration for Inventory Management

This configuration file sets up the inventory app with proper signal handling,
automatic migrations, and integration with your existing core system.

The inventory app is designed to be the central hub for all product and stock
management operations, providing real-time inventory tracking, automated
reorder management, and comprehensive business intelligence.
"""

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """
    Configuration for the Inventory Management application.
    
    This app provides comprehensive inventory management capabilities including:
    - Real-time stock tracking across multiple locations
    - Automated reorder point management
    - Supplier relationship management
    - Purchase order workflow
    - Stock movement audit trails
    - Physical inventory reconciliation
    - Cost tracking and profit analysis
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory Management'
    
    def ready(self):
        """
        Called when the application is ready.
        
        This method imports signals to ensure they're properly registered
        and sets up any necessary inventory management automation.
        """
        # Import signals to ensure they're registered
        import inventory.signals
        
        # Import any background task configurations
        try:
            from . import tasks
        except ImportError:
            # Tasks module is optional for basic functionality
            pass
        
        # Initialize inventory management features
        self._initialize_inventory_features()
    
    def _initialize_inventory_features(self):
        """
        Initialize inventory management features and automation.
        
        This method sets up automated features like:
        - Reorder alert monitoring
        - Stock level synchronization
        - Performance metric tracking
        """
        # Set up any periodic tasks or automation
        # This could include scheduling periodic stock level checks,
        # reorder alert generation, or performance metric updates
        
        # For now, we'll just log that the inventory system is ready
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Inventory Management System initialized successfully")
