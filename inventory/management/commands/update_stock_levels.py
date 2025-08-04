# inventory/management/commands/update_stock_levels.py

"""
Django Management Command for Batch Stock Level Updates

This command provides comprehensive stock level management and synchronization
capabilities. It's designed to handle bulk stock updates, reconciliation,
and maintenance operations while maintaining data integrity.

Key Features:
- Batch stock level updates from CSV/Excel files
- Stock reconciliation and synchronization
- Location-based stock adjustments
- Automated reorder alert generation
- Comprehensive audit trail creation
- Integration with existing stock movement system

Usage Examples:
    python manage.py update_stock_levels --reconcile-all
    python manage.py update_stock_levels --import-file stock_update.csv
    python manage.py update_stock_levels --set-reorder-levels
    python manage.py update_stock_levels --generate-alerts
"""

import csv
import json
import os
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone

from inventory.models import Product, StockLevel, Location, StockMovement, ReorderAlert
from inventory.utils import create_stock_movement


class Command(BaseCommand):
    help = 'Update stock levels with various batch operations and reconciliation'
    
    def add_arguments(self, parser):
        # Operation modes
        parser.add_argument(
            '--reconcile-all',
            action='store_true',
            help='Reconcile all product stock levels with location totals'
        )
        
        parser.add_argument(
            '--import-file',
            type=str,
            help='Import stock levels from CSV file'
        )
        
        parser.add_argument(
            '--set-reorder-levels',
            action='store_true',
            help='Update reorder levels based on sales history'
        )
        
        parser.add_argument(
            '--generate-alerts',
            action='store_true',
            help='Generate reorder alerts for products below reorder level'
        )
        
        parser.add_argument(
            '--sync-locations',
            action='store_true',
            help='Synchronize stock levels across all locations'
        )
        
        parser.add_argument(
            '--zero-negative-stock',
            action='store_true',
            help='Set negative stock levels to zero with adjustment records'
        )
        
        # Filtering options
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category name'
        )
        
        parser.add_argument(
            '--supplier',
            type=str,
            help='Filter by supplier name'
        )
        
        parser.add_argument(
            '--location',
            type=str,
            help='Filter by location name'
        )
        
        parser.add_argument(
            '--sku-pattern',
            type=str,
            help='Filter by SKU pattern (supports wildcards)'
        )
        
        # Operation options
        parser.add_argument(
            '--user',
            type=str,
            default='system',
            help='Username to assign for stock movements'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform validation without making changes'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of products to process in each batch'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force operations that might normally be blocked'
        )
        
        parser.add_argument(
            '--reason',
            type=str,
            default='Batch stock update',
            help='Reason for stock adjustments'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        # Get user for operations
        user = self._get_user(options['user'])
        
        # Display configuration
        self._display_config(options, user)
        
        # Execute requested operations
        try:
            if options['reconcile_all']:
                self._reconcile_all_stock(options, user)
            
            if options['import_file']:
                self._import_stock_levels(options['import_file'], options, user)
            
            if options['set_reorder_levels']:
                self._update_reorder_levels(options, user)
            
            if options['generate_alerts']:
                self._generate_reorder_alerts(options, user)
            
            if options['sync_locations']:
                self._sync_location_stock(options, user)
            
            if options['zero_negative_stock']:
                self._zero_negative_stock(options, user)
            
            self.stdout.write(
                self.style.SUCCESS('Stock level update operations completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Operation failed: {str(e)}')
            )
            if options['verbosity'] >= 2:
                import traceback
                self.stdout.write(traceback.format_exc())
            raise
    
    def _get_user(self, username):
        """Get user for operation attribution"""
        if username == 'system':
            return None
        
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            # Try to find an admin user
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" not found. Using {admin_user.username}')
                )
                return admin_user
            else:
                raise CommandError(f'User "{username}" not found and no admin user available')
    
    def _display_config(self, options, user):
        """Display operation configuration"""
        self.stdout.write(self.style.SUCCESS('=== Stock Level Update Configuration ==='))
        self.stdout.write(f'User: {user.username if user else "System"}')
        self.stdout.write(f'Dry run: {options["dry_run"]}')
        self.stdout.write(f'Batch size: {options["batch_size"]}')
        self.stdout.write(f'Reason: {options["reason"]}')
        
        # Show active filters
        filters = []
        if options['category']:
            filters.append(f'Category: {options["category"]}')
        if options['supplier']:
            filters.append(f'Supplier: {options["supplier"]}')
        if options['location']:
            filters.append(f'Location: {options["location"]}')
        if options['sku_pattern']:
            filters.append(f'SKU Pattern: {options["sku_pattern"]}')
        
        if filters:
            self.stdout.write(f'Filters: {", ".join(filters)}')
        
        self.stdout.write('')
    
    def _get_filtered_products(self, options):
        """Get products based on filter criteria"""
        queryset = Product.objects.filter(is_active=True)
        
        # Apply filters
        if options['category']:
            queryset = queryset.filter(category__name__icontains=options['category'])
        
        if options['supplier']:
            queryset = queryset.filter(supplier__name__icontains=options['supplier'])
        
        if options['sku_pattern']:
            pattern = options['sku_pattern'].replace('*', '%')
            queryset = queryset.extra(where=["sku LIKE %s"], params=[pattern])
        
        return queryset.select_related('category', 'supplier')
    
    def _reconcile_all_stock(self, options, user):
        """Reconcile product stock levels with location totals"""
        self.stdout.write(self.style.SUCCESS('=== Reconciling Stock Levels ==='))
        
        products = self._get_filtered_products(options)
        total_products = products.count()
        reconciled_count = 0
        discrepancy_count = 0
        
        self.stdout.write(f'Processing {total_products} products...')
        
        for i, product in enumerate(products, 1):
            # Calculate total stock from all locations
            location_total = StockLevel.objects.filter(product=product).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            current_stock = product.current_stock
            
            if location_total != current_stock:
                discrepancy = location_total - current_stock
                discrepancy_count += 1
                
                self.stdout.write(
                    f'Discrepancy found for {product.sku}: '
                    f'System: {current_stock}, Locations: {location_total}, '
                    f'Difference: {discrepancy:+d}'
                )
                
                if not options['dry_run']:
                    # Update product stock level
                    old_stock = product.current_stock
                    product.current_stock = location_total
                    product.save(update_fields=['current_stock', 'available_stock'])
                    
                    # Create stock movement record
                    create_stock_movement(
                        product=product,
                        movement_type='adjustment',
                        quantity=discrepancy,
                        reference=f'Stock reconciliation: {options["reason"]}',
                        user=user,
                        notes=f'Reconciled stock levels. System: {old_stock}, Locations: {location_total}'
                    )
                    
                    reconciled_count += 1
            
            # Progress indicator
            if i % 100 == 0:
                self.stdout.write(f'Processed {i}/{total_products} products...')
        
        self.stdout.write('')
        self.stdout.write(f'Reconciliation complete:')
        self.stdout.write(f'  Products processed: {total_products}')
        self.stdout.write(f'  Discrepancies found: {discrepancy_count}')
        if not options['dry_run']:
            self.stdout.write(f'  Products reconciled: {reconciled_count}')
        self.stdout.write('')
    
    def _import_stock_levels(self, file_path, options, user):
        """Import stock levels from CSV file"""
        self.stdout.write(self.style.SUCCESS('=== Importing Stock Levels ==='))
        
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')
        
        results = {
            'total_rows': 0,
            'processed': 0,
            'updated': 0,
            'errors': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate headers
                required_headers = ['sku', 'quantity']
                optional_headers = ['location', 'reason', 'reference']
                
                missing_headers = [h for h in required_headers if h not in reader.fieldnames]
                if missing_headers:
                    raise CommandError(f'Missing required headers: {", ".join(missing_headers)}')
                
                self.stdout.write(f'File headers: {", ".join(reader.fieldnames)}')
                self.stdout.write('')
                
                batch = []
                batch_size = options['batch_size']
                
                for row_num, row in enumerate(reader, start=2):
                    results['total_rows'] += 1
                    
                    try:
                        # Clean and validate row data
                        sku = row['sku'].strip()
                        quantity = int(float(row['quantity']))
                        location_name = row.get('location', '').strip()
                        reason = row.get('reason', options['reason']).strip()
                        reference = row.get('reference', f'Import row {row_num}').strip()
                        
                        batch.append({
                            'row_num': row_num,
                            'sku': sku,
                            'quantity': quantity,
                            'location_name': location_name,
                            'reason': reason,
                            'reference': reference
                        })
                        
                        # Process batch when full
                        if len(batch) >= batch_size:
                            self._process_import_batch(batch, options, user, results)
                            batch = []
                    
                    except (ValueError, KeyError) as e:
                        results['errors'].append(f'Row {row_num}: {str(e)}')
                    
                    # Progress indicator
                    if results['total_rows'] % 100 == 0:
                        self.stdout.write(f'Processed {results["total_rows"]} rows...')
                
                # Process remaining batch
                if batch:
                    self._process_import_batch(batch, options, user, results)
        
        except Exception as e:
            raise CommandError(f'Error reading import file: {str(e)}')
        
        # Display results
        self.stdout.write('')
        self.stdout.write(f'Import results:')
        self.stdout.write(f'  Total rows: {results["total_rows"]}')
        self.stdout.write(f'  Successfully processed: {results["processed"]}')
        if not options['dry_run']:
            self.stdout.write(f'  Stock levels updated: {results["updated"]}')
        
        if results['errors']:
            self.stdout.write(f'  Errors: {len(results["errors"])}')
            for error in results['errors'][:10]:  # Show first 10 errors
                self.stdout.write(f'    {error}')
            if len(results['errors']) > 10:
                self.stdout.write(f'    ... and {len(results["errors"]) - 10} more')
        
        self.stdout.write('')
    
    def _process_import_batch(self, batch, options, user, results):
        """Process a batch of import records"""
        if options['dry_run']:
            # Just validate in dry run mode
            for item in batch:
                if self._validate_import_item(item, results):
                    results['processed'] += 1
        else:
            # Actually update stock levels
            with transaction.atomic():
                for item in batch:
                    if self._update_stock_from_import(item, options, user, results):
                        results['processed'] += 1
                        results['updated'] += 1
    
    def _validate_import_item(self, item, results):
        """Validate import item without making changes"""
        try:
            # Check if product exists
            if not Product.objects.filter(sku=item['sku'], is_active=True).exists():
                results['errors'].append(f'Row {item["row_num"]}: Product {item["sku"]} not found')
                return False
            
            # Check if location exists (if specified)
            if item['location_name']:
                if not Location.objects.filter(name=item['location_name'], is_active=True).exists():
                    results['errors'].append(f'Row {item["row_num"]}: Location {item["location_name"]} not found')
                    return False
            
            return True
            
        except Exception as e:
            results['errors'].append(f'Row {item["row_num"]}: Validation error - {str(e)}')
            return False
    
    def _update_stock_from_import(self, item, options, user, results):
        """Update stock level from import item"""
        try:
            # Get product
            product = Product.objects.get(sku=item['sku'], is_active=True)
            
            # Get location if specified
            location = None
            if item['location_name']:
                location = Location.objects.get(name=item['location_name'], is_active=True)
            
            # Calculate adjustment needed
            current_stock = product.current_stock
            target_quantity = item['quantity']
            adjustment = target_quantity - current_stock
            
            if adjustment != 0:
                # Create stock movement
                create_stock_movement(
                    product=product,
                    movement_type='adjustment',
                    quantity=adjustment,
                    reference=item['reference'],
                    to_location=location if adjustment > 0 else None,
                    from_location=location if adjustment < 0 else None,
                    user=user,
                    notes=f"Import adjustment: {item['reason']}"
                )
                
                if options['verbosity'] >= 2:
                    self.stdout.write(
                        f'Updated {product.sku}: {current_stock} → {target_quantity} '
                        f'({adjustment:+d})'
                    )
            
            return True
            
        except Exception as e:
            results['errors'].append(f'Row {item["row_num"]}: Update error - {str(e)}')
            return False
    
    def _update_reorder_levels(self, options, user):
        """Update reorder levels based on sales history"""
        self.stdout.write(self.style.SUCCESS('=== Updating Reorder Levels ==='))
        
        from inventory.utils import estimate_annual_demand, calculate_optimal_order_quantity
        
        products = self._get_filtered_products(options)
        updated_count = 0
        
        for product in products:
            try:
                # Calculate new reorder level based on demand
                annual_demand = estimate_annual_demand(product)
                
                if annual_demand > 0:
                    # Calculate safety stock (e.g., 2 weeks of demand)
                    safety_stock = max(1, int(annual_demand / 26))  # 26 fortnights in a year
                    
                    # Lead time demand
                    lead_time_demand = int(
                        (annual_demand / 365) * product.supplier_lead_time_days
                    )
                    
                    # New reorder level = lead time demand + safety stock
                    new_reorder_level = lead_time_demand + safety_stock
                    
                    # Don't make dramatic changes
                    old_reorder_level = product.reorder_level
                    max_change = max(old_reorder_level * 0.5, 10)  # Max 50% change or 10 units
                    
                    if abs(new_reorder_level - old_reorder_level) > max_change:
                        if new_reorder_level > old_reorder_level:
                            new_reorder_level = old_reorder_level + max_change
                        else:
                            new_reorder_level = max(1, old_reorder_level - max_change)
                    
                    new_reorder_level = int(new_reorder_level)
                    
                    if new_reorder_level != old_reorder_level and not options['dry_run']:
                        product.reorder_level = new_reorder_level
                        
                        # Also update reorder quantity
                        optimal_qty = calculate_optimal_order_quantity(product)
                        product.reorder_quantity = optimal_qty
                        
                        product.save(update_fields=['reorder_level', 'reorder_quantity'])
                        updated_count += 1
                        
                        if options['verbosity'] >= 2:
                            self.stdout.write(
                                f'Updated {product.sku}: Reorder level {old_reorder_level} → {new_reorder_level}, '
                                f'Quantity: {optimal_qty}'
                            )
            
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error updating reorder level for {product.sku}: {str(e)}')
                )
        
        self.stdout.write('')
        self.stdout.write(f'Reorder level update complete:')
        self.stdout.write(f'  Products processed: {products.count()}')
        if not options['dry_run']:
            self.stdout.write(f'  Reorder levels updated: {updated_count}')
        self.stdout.write('')
    
    def _generate_reorder_alerts(self, options, user):
        """Generate reorder alerts for products below reorder level"""
        self.stdout.write(self.style.SUCCESS('=== Generating Reorder Alerts ==='))
        
        products = self._get_filtered_products(options).filter(
            current_stock__lte=models.F('reorder_level')
        )
        
        alert_count = 0
        
        for product in products:
            # Check if there's already an active alert
            existing_alert = ReorderAlert.objects.filter(
                product=product,
                status__in=['active', 'acknowledged']
            ).exists()
            
            if not existing_alert:
                # Determine priority
                stock_ratio = product.current_stock / max(product.reorder_level, 1)
                if stock_ratio <= 0:
                    priority = 'critical'
                elif stock_ratio <= 0.5:
                    priority = 'high'
                elif stock_ratio <= 0.8:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                if not options['dry_run']:
                    ReorderAlert.objects.create(
                        product=product,
                        priority=priority,
                        current_stock=product.current_stock,
                        reorder_level=product.reorder_level,
                        suggested_order_quantity=product.reorder_quantity,
                        suggested_supplier=product.supplier,
                        estimated_cost=product.reorder_quantity * product.cost_price
                    )
                
                alert_count += 1
                
                if options['verbosity'] >= 2:
                    self.stdout.write(
                        f'Created {priority} alert for {product.sku} '
                        f'(stock: {product.current_stock}, reorder: {product.reorder_level})'
                    )
        
        self.stdout.write('')
        self.stdout.write(f'Reorder alert generation complete:')
        self.stdout.write(f'  Products below reorder level: {products.count()}')
        if not options['dry_run']:
            self.stdout.write(f'  New alerts created: {alert_count}')
        self.stdout.write('')
    
    def _sync_location_stock(self, options, user):
        """Synchronize stock levels across locations"""
        self.stdout.write(self.style.SUCCESS('=== Synchronizing Location Stock ==='))
        
        # Create missing stock level records
        missing_count = 0
        
        active_products = Product.objects.filter(is_active=True)
        active_locations = Location.objects.filter(is_active=True)
        
        for product in active_products:
            for location in active_locations:
                stock_level, created = StockLevel.objects.get_or_create(
                    product=product,
                    location=location,
                    defaults={
                        'quantity': 0,
                        'reserved_quantity': 0
                    }
                )
                
                if created:
                    missing_count += 1
        
        self.stdout.write(f'Created {missing_count} missing stock level records')
        self.stdout.write('')
    
    def _zero_negative_stock(self, options, user):
        """Set negative stock levels to zero with adjustment records"""
        self.stdout.write(self.style.SUCCESS('=== Zeroing Negative Stock ==='))
        
        negative_products = self._get_filtered_products(options).filter(
            current_stock__lt=0
        )
        
        zeroed_count = 0
        
        for product in negative_products:
            negative_stock = product.current_stock
            
            self.stdout.write(
                f'Found negative stock for {product.sku}: {negative_stock}'
            )
            
            if not options['dry_run']:
                # Create adjustment to zero
                adjustment = -negative_stock
                
                create_stock_movement(
                    product=product,
                    movement_type='adjustment',
                    quantity=adjustment,
                    reference=f'Zero negative stock: {options["reason"]}',
                    user=user,
                    notes=f'Adjusted negative stock from {negative_stock} to 0'
                )
                
                zeroed_count += 1
        
        self.stdout.write('')
        self.stdout.write(f'Negative stock correction complete:')
        self.stdout.write(f'  Products with negative stock: {negative_products.count()}')
        if not options['dry_run']:
            self.stdout.write(f'  Products corrected: {zeroed_count}')
        self.stdout.write('')
