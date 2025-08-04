# inventory/management/commands/import_products.py

"""
Django Management Command for Bulk Product Import

This command provides powerful bulk import capabilities for products from
CSV and Excel files. It's designed to handle large datasets efficiently
while maintaining data integrity and providing detailed feedback.

Key Features:
- Support for CSV and Excel formats
- Intelligent data validation and cleanup
- Duplicate detection and handling
- Category and supplier auto-creation
- Detailed import reporting
- Rollback on critical errors
- Integration with existing inventory system

Usage Examples:
    python manage.py import_products products.csv --update-existing
    python manage.py import_products products.xlsx --dry-run
    python manage.py import_products data.csv --category-mapping=mapping.json
"""

import csv
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from django.utils.text import slugify

from inventory.models import Product, Category, Supplier
from inventory.utils import import_products_from_csv


class Command(BaseCommand):
    help = 'Import products from CSV or Excel file with comprehensive validation and reporting'
    
    def add_arguments(self, parser):
        # Required arguments
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the CSV or Excel file to import'
        )
        
        # Optional flags
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing products instead of skipping them'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform validation without making changes to the database'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            default='system',
            help='Username to assign as creator of imported products'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of products to process in each batch (default: 100)'
        )
        
        parser.add_argument(
            '--category-mapping',
            type=str,
            help='JSON file mapping category names to existing categories'
        )
        
        parser.add_argument(
            '--supplier-mapping',
            type=str,
            help='JSON file mapping supplier names to existing suppliers'
        )
        
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip detailed validation (faster but less safe)'
        )
        
        parser.add_argument(
            '--create-categories',
            action='store_true',
            help='Automatically create missing categories'
        )
        
        parser.add_argument(
            '--create-suppliers',
            action='store_true',
            help='Automatically create missing suppliers'
        )
        
        parser.add_argument(
            '--encoding',
            type=str,
            default='utf-8',
            help='File encoding (default: utf-8)'
        )
        
        parser.add_argument(
            '--delimiter',
            type=str,
            default=',',
            help='CSV delimiter (default: comma)'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        file_path = options['file_path']
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')
        
        # Determine file type
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in ['.csv', '.xlsx', '.xls']:
            raise CommandError(f'Unsupported file type: {file_extension}. Use CSV or Excel files.')
        
        # Get user for import attribution
        user = self._get_import_user(options['user'])
        
        # Load mappings if provided
        category_mapping = self._load_mapping(options.get('category_mapping'))
        supplier_mapping = self._load_mapping(options.get('supplier_mapping'))
        
        # Display import configuration
        self._display_import_config(options, file_path, user)
        
        try:
            if file_extension == '.csv':
                results = self._import_csv(file_path, options, user, category_mapping, supplier_mapping)
            else:
                results = self._import_excel(file_path, options, user, category_mapping, supplier_mapping)
            
            # Display results
            self._display_results(results, options['dry_run'])
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Import failed: {str(e)}')
            )
            if options['verbosity'] >= 2:
                import traceback
                self.stdout.write(traceback.format_exc())
            sys.exit(1)
    
    def _get_import_user(self, username):
        """Get or validate the user for import attribution"""
        if username == 'system':
            return None
        
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            # Try to find admin user
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" not found. Using {admin_user.username}')
                )
                return admin_user
            else:
                raise CommandError(f'User "{username}" not found and no admin user available')
    
    def _load_mapping(self, mapping_file):
        """Load mapping file if provided"""
        if not mapping_file:
            return {}
        
        if not os.path.exists(mapping_file):
            raise CommandError(f'Mapping file not found: {mapping_file}')
        
        try:
            with open(mapping_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise CommandError(f'Error reading mapping file: {str(e)}')
    
    def _display_import_config(self, options, file_path, user):
        """Display import configuration"""
        self.stdout.write(self.style.SUCCESS('=== Product Import Configuration ==='))
        self.stdout.write(f'File: {file_path}')
        self.stdout.write(f'User: {user.username if user else "System"}')
        self.stdout.write(f'Update existing: {options["update_existing"]}')
        self.stdout.write(f'Dry run: {options["dry_run"]}')
        self.stdout.write(f'Batch size: {options["batch_size"]}')
        self.stdout.write(f'Create categories: {options["create_categories"]}')
        self.stdout.write(f'Create suppliers: {options["create_suppliers"]}')
        self.stdout.write('')
    
    def _import_csv(self, file_path, options, user, category_mapping, supplier_mapping):
        """Import products from CSV file"""
        results = {
            'total_rows': 0,
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            with open(file_path, 'r', encoding=options['encoding']) as csvfile:
                # Detect delimiter if not specified
                delimiter = options['delimiter']
                if delimiter == ',':
                    # Try to detect delimiter
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    sniffer = csv.Sniffer()
                    try:
                        delimiter = sniffer.sniff(sample).delimiter
                    except:
                        delimiter = ','
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                # Validate headers
                required_headers = ['name', 'sku', 'category', 'supplier']
                missing_headers = [h for h in required_headers if h not in reader.fieldnames]
                if missing_headers:
                    raise CommandError(f'Missing required headers: {", ".join(missing_headers)}')
                
                self.stdout.write(f'Found headers: {", ".join(reader.fieldnames)}')
                self.stdout.write('')
                
                # Process in batches
                batch = []
                batch_size = options['batch_size']
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    results['total_rows'] += 1
                    
                    # Clean and validate row data
                    cleaned_row = self._clean_row_data(row, row_num, results)
                    if cleaned_row:
                        batch.append((row_num, cleaned_row))
                    
                    # Process batch when full
                    if len(batch) >= batch_size:
                        self._process_batch(batch, options, user, category_mapping, supplier_mapping, results)
                        batch = []
                    
                    # Progress indicator
                    if results['total_rows'] % 100 == 0:
                        self.stdout.write(f'Processed {results["total_rows"]} rows...')
                
                # Process remaining batch
                if batch:
                    self._process_batch(batch, options, user, category_mapping, supplier_mapping, results)
        
        except UnicodeDecodeError as e:
            raise CommandError(f'Encoding error: {str(e)}. Try specifying --encoding parameter.')
        except Exception as e:
            raise CommandError(f'Error reading CSV file: {str(e)}')
        
        return results
    
    def _import_excel(self, file_path, options, user, category_mapping, supplier_mapping):
        """Import products from Excel file"""
        try:
            import pandas as pd
        except ImportError:
            raise CommandError('pandas is required for Excel import. Install with: pip install pandas openpyxl')
        
        results = {
            'total_rows': 0,
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Validate headers
            required_headers = ['name', 'sku', 'category', 'supplier']
            missing_headers = [h for h in required_headers if h not in df.columns]
            if missing_headers:
                raise CommandError(f'Missing required headers: {", ".join(missing_headers)}')
            
            self.stdout.write(f'Found headers: {", ".join(df.columns)}')
            self.stdout.write(f'Total rows: {len(df)}')
            self.stdout.write('')
            
            # Process in batches
            batch_size = options['batch_size']
            
            for start_idx in range(0, len(df), batch_size):
                end_idx = min(start_idx + batch_size, len(df))
                batch_df = df.iloc[start_idx:end_idx]
                
                batch = []
                for idx, row in batch_df.iterrows():
                    row_num = idx + 2  # +2 for header and 0-based index
                    results['total_rows'] += 1
                    
                    # Convert pandas Series to dict and clean
                    row_dict = row.to_dict()
                    cleaned_row = self._clean_row_data(row_dict, row_num, results)
                    if cleaned_row:
                        batch.append((row_num, cleaned_row))
                
                # Process batch
                if batch:
                    self._process_batch(batch, options, user, category_mapping, supplier_mapping, results)
                
                # Progress indicator
                self.stdout.write(f'Processed {end_idx} of {len(df)} rows...')
        
        except Exception as e:
            raise CommandError(f'Error reading Excel file: {str(e)}')
        
        return results
    
    def _clean_row_data(self, row, row_num, results):
        """Clean and validate row data"""
        try:
            # Clean string fields
            cleaned = {}
            
            # Required fields
            for field in ['name', 'sku', 'category', 'supplier']:
                value = str(row.get(field, '')).strip()
                if not value or value.lower() == 'nan':
                    results['errors'].append(f'Row {row_num}: Missing required field "{field}"')
                    return None
                cleaned[field] = value
            
            # Optional string fields
            for field in ['description', 'brand', 'model_number', 'barcode']:
                value = str(row.get(field, '')).strip()
                cleaned[field] = value if value and value.lower() != 'nan' else ''
            
            # Numeric fields
            cleaned['cost_price'] = self._clean_decimal(row.get('cost_price', 0))
            cleaned['selling_price'] = self._clean_decimal(row.get('selling_price', 0))
            cleaned['reorder_level'] = self._clean_integer(row.get('reorder_level', 10))
            cleaned['reorder_quantity'] = self._clean_integer(row.get('reorder_quantity', 50))
            cleaned['current_stock'] = self._clean_integer(row.get('current_stock', 0))
            
            # Boolean fields
            cleaned['is_active'] = self._clean_boolean(row.get('is_active', True))
            
            return cleaned
            
        except Exception as e:
            results['errors'].append(f'Row {row_num}: Data cleaning error - {str(e)}')
            return None
    
    def _clean_decimal(self, value):
        """Clean decimal value"""
        if value is None or str(value).strip() == '' or str(value).lower() == 'nan':
            return Decimal('0.00')
        
        try:
            # Remove currency symbols and whitespace
            clean_value = str(value).replace('$', '').replace(',', '').strip()
            return Decimal(clean_value)
        except (InvalidOperation, ValueError):
            return Decimal('0.00')
    
    def _clean_integer(self, value):
        """Clean integer value"""
        if value is None or str(value).strip() == '' or str(value).lower() == 'nan':
            return 0
        
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _clean_boolean(self, value):
        """Clean boolean value"""
        if isinstance(value, bool):
            return value
        
        str_value = str(value).lower().strip()
        return str_value in ['true', 'yes', '1', 'y', 'active', 'on']
    
    def _process_batch(self, batch, options, user, category_mapping, supplier_mapping, results):
        """Process a batch of products"""
        if options['dry_run']:
            # In dry run mode, just validate without saving
            for row_num, row_data in batch:
                self._validate_product_data(row_data, row_num, category_mapping, supplier_mapping, results)
                results['processed'] += 1
        else:
            # Actually create/update products
            with transaction.atomic():
                for row_num, row_data in batch:
                    success = self._create_or_update_product(
                        row_data, row_num, options, user, category_mapping, supplier_mapping, results
                    )
                    if success:
                        results['processed'] += 1
    
    def _validate_product_data(self, row_data, row_num, category_mapping, supplier_mapping, results):
        """Validate product data without creating records"""
        # Check if SKU already exists
        if Product.objects.filter(sku=row_data['sku']).exists():
            results['warnings'].append(f'Row {row_num}: SKU "{row_data["sku"]}" already exists')
        
        # Validate category
        category_name = row_data['category']
        mapped_category = category_mapping.get(category_name, category_name)
        if not Category.objects.filter(name=mapped_category).exists():
            results['warnings'].append(f'Row {row_num}: Category "{mapped_category}" does not exist')
        
        # Validate supplier
        supplier_name = row_data['supplier']
        mapped_supplier = supplier_mapping.get(supplier_name, supplier_name)
        if not Supplier.objects.filter(name=mapped_supplier).exists():
            results['warnings'].append(f'Row {row_num}: Supplier "{mapped_supplier}" does not exist')
    
    def _create_or_update_product(self, row_data, row_num, options, user, category_mapping, supplier_mapping, results):
        """Create or update a product"""
        try:
            # Get or create category
            category_name = row_data['category']
            mapped_category = category_mapping.get(category_name, category_name)
            
            try:
                category = Category.objects.get(name=mapped_category)
            except Category.DoesNotExist:
                if options['create_categories']:
                    category = Category.objects.create(
                        name=mapped_category,
                        slug=slugify(mapped_category)
                    )
                    results['warnings'].append(f'Row {row_num}: Created category "{mapped_category}"')
                else:
                    results['errors'].append(f'Row {row_num}: Category "{mapped_category}" does not exist')
                    return False
            
            # Get or create supplier
            supplier_name = row_data['supplier']
            mapped_supplier = supplier_mapping.get(supplier_name, supplier_name)
            
            try:
                supplier = Supplier.objects.get(name=mapped_supplier)
            except Supplier.DoesNotExist:
                if options['create_suppliers']:
                    supplier = Supplier.objects.create(
                        name=mapped_supplier,
                        supplier_code=f"SUP-{mapped_supplier[:3].upper()}",
                        email=f"info@{mapped_supplier.lower().replace(' ', '')}.com"
                    )
                    results['warnings'].append(f'Row {row_num}: Created supplier "{mapped_supplier}"')
                else:
                    results['errors'].append(f'Row {row_num}: Supplier "{mapped_supplier}" does not exist')
                    return False
            
            # Check if product exists
            existing_product = Product.objects.filter(sku=row_data['sku']).first()
            
            if existing_product:
                if options['update_existing']:
                    # Update existing product
                    for field, value in row_data.items():
                        if field not in ['category', 'supplier']:
                            setattr(existing_product, field, value)
                    
                    existing_product.category = category
                    existing_product.supplier = supplier
                    existing_product.save()
                    
                    results['updated'] += 1
                    if options['verbosity'] >= 2:
                        self.stdout.write(f'Updated: {existing_product.sku}')
                else:
                    results['skipped'] += 1
                    if options['verbosity'] >= 2:
                        self.stdout.write(f'Skipped: {row_data["sku"]} (already exists)')
            else:
                # Create new product
                product_data = row_data.copy()
                product_data['category'] = category
                product_data['supplier'] = supplier
                product_data['created_by'] = user
                
                product = Product.objects.create(**product_data)
                results['created'] += 1
                
                if options['verbosity'] >= 2:
                    self.stdout.write(f'Created: {product.sku}')
            
            return True
            
        except Exception as e:
            results['errors'].append(f'Row {row_num}: {str(e)}')
            return False
    
    def _display_results(self, results, dry_run):
        """Display import results"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Import Results ==='))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made to database'))
        
        self.stdout.write(f'Total rows processed: {results["total_rows"]}')
        self.stdout.write(f'Successfully processed: {results["processed"]}')
        
        if not dry_run:
            self.stdout.write(f'Products created: {results["created"]}')
            self.stdout.write(f'Products updated: {results["updated"]}')
            self.stdout.write(f'Products skipped: {results["skipped"]}')
        
        # Display warnings
        if results['warnings']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'Warnings ({len(results["warnings"])}):'))
            for warning in results['warnings'][:20]:  # Limit to first 20
                self.stdout.write(self.style.WARNING(f'  {warning}'))
            if len(results['warnings']) > 20:
                self.stdout.write(self.style.WARNING(f'  ... and {len(results["warnings"]) - 20} more'))
        
        # Display errors
        if results['errors']:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f'Errors ({len(results["errors"])}):'))
            for error in results['errors'][:20]:  # Limit to first 20
                self.stdout.write(self.style.ERROR(f'  {error}'))
            if len(results['errors']) > 20:
                self.stdout.write(self.style.ERROR(f'  ... and {len(results["errors"]) - 20} more'))
        
        # Final status
        self.stdout.write('')
        if results['errors']:
            self.stdout.write(
                self.style.WARNING('Import completed with errors. Review the error list above.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Import completed successfully!')
            )
