# inventory/management/commands/generate_stock_report.py

"""
Django Management Command for Comprehensive Stock Reporting

This command provides a complete automated reporting solution for inventory
management. It generates various types of reports with flexible scheduling,
multiple output formats, and intelligent data analysis capabilities.

Key Features:
- Multiple report types (valuation, movement, reorder, ABC analysis, etc.)
- Flexible output formats (CSV, PDF, JSON, HTML)
- Automated scheduling and email delivery
- Advanced filtering and date range options
- Performance analytics and KPI calculations
- Integration with existing notification system
- Comprehensive audit trail and logging

Report Types Available:
- Inventory Valuation: Current stock values by category/location
- Stock Movement: Historical movement analysis and trends
- Reorder Analysis: Products requiring reorder with recommendations
- ABC Analysis: Product classification based on value/movement
- Stock Aging: Slow-moving and dead stock identification
- Supplier Performance: Lead times, reliability, cost analysis
- Low Stock Alerts: Critical stock level warnings
- Category Performance: Sales and profitability by category
- Location Analysis: Stock distribution and efficiency
- Custom Reports: User-defined report parameters

Usage Examples:
    python manage.py generate_stock_report --report-type=valuation --format=csv
    python manage.py generate_stock_report --report-type=reorder --email=manager@company.com
    python manage.py generate_stock_report --report-type=abc --period=90 --format=pdf
    python manage.py generate_stock_report --schedule=daily --report-type=low-stock
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models import Q, Sum, Count, Avg, F, Case, When, Max, Min
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

from inventory.models import (
    Product, Category, Supplier, Location, StockLevel, StockMovement,
    PurchaseOrder, ReorderAlert
)
from inventory.utils import (
    calculate_stock_value, generate_abc_analysis, calculate_inventory_turnover,
    generate_stock_valuation_report
)


class Command(BaseCommand):
    help = 'Generate comprehensive stock reports with automated scheduling and delivery'
    
    def add_arguments(self, parser):
        # Report type - the core parameter
        parser.add_argument(
            '--report-type',
            type=str,
            required=True,
            choices=[
                'valuation', 'movement', 'reorder', 'abc', 'aging',
                'supplier', 'low-stock', 'category', 'location', 'custom'
            ],
            help='Type of report to generate'
        )
        
        # Output format options
        parser.add_argument(
            '--format',
            type=str,
            default='csv',
            choices=['csv', 'pdf', 'json', 'html', 'xlsx'],
            help='Output format for the report (default: csv)'
        )
        
        parser.add_argument(
            '--output-file',
            type=str,
            help='Custom output file path (auto-generated if not specified)'
        )
        
        # Date range and period options
        parser.add_argument(
            '--period',
            type=int,
            default=30,
            help='Period in days for analysis (default: 30)'
        )
        
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date for analysis (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date for analysis (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--as-of-date',
            type=str,
            help='Point-in-time date for valuation reports (YYYY-MM-DD format)'
        )
        
        # Filtering options
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category name or ID'
        )
        
        parser.add_argument(
            '--supplier',
            type=str,
            help='Filter by supplier name or ID'
        )
        
        parser.add_argument(
            '--location',
            type=str,
            help='Filter by location name or ID'
        )
        
        parser.add_argument(
            '--sku-pattern',
            type=str,
            help='Filter by SKU pattern (supports wildcards)'
        )
        
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive products in the report'
        )
        
        # Analysis options
        parser.add_argument(
            '--abc-criteria',
            type=str,
            default='revenue',
            choices=['revenue', 'quantity', 'profit'],
            help='Criteria for ABC analysis (default: revenue)'
        )
        
        parser.add_argument(
            '--aging-periods',
            type=str,
            default='30,60,90,180',
            help='Aging periods in days, comma-separated (default: 30,60,90,180)'
        )
        
        parser.add_argument(
            '--min-value',
            type=float,
            help='Minimum stock value threshold for inclusion'
        )
        
        parser.add_argument(
            '--max-value',
            type=float,
            help='Maximum stock value threshold for inclusion'
        )
        
        # Email and delivery options
        parser.add_argument(
            '--email',
            type=str,
            help='Email address(es) to send the report (comma-separated)'
        )
        
        parser.add_argument(
            '--email-subject',
            type=str,
            help='Custom email subject line'
        )
        
        parser.add_argument(
            '--schedule',
            type=str,
            choices=['daily', 'weekly', 'monthly', 'quarterly'],
            help='Schedule for automated report generation'
        )
        
        # Advanced options
        parser.add_argument(
            '--include-costs',
            action='store_true',
            help='Include cost information in reports (requires permission)'
        )
        
        parser.add_argument(
            '--group-by',
            type=str,
            choices=['category', 'supplier', 'location', 'none'],
            default='none',
            help='Group report data by specified dimension'
        )
        
        parser.add_argument(
            '--sort-by',
            type=str,
            default='name',
            help='Sort order for report data'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records in the report'
        )
        
        parser.add_argument(
            '--save-config',
            type=str,
            help='Save report configuration to file for reuse'
        )
        
        parser.add_argument(
            '--load-config',
            type=str,
            help='Load report configuration from file'
        )
    
    def handle(self, *args, **options):
        """Main command handler orchestrating report generation"""
        try:
            # Load configuration if specified
            if options['load_config']:
                options = self._load_configuration(options['load_config'], options)
            
            # Validate and process options
            self._validate_options(options)
            processed_options = self._process_options(options)
            
            # Display configuration
            self._display_configuration(processed_options)
            
            # Generate the requested report
            report_data = self._generate_report(processed_options)
            
            # Process and format the output
            output_file = self._generate_output(report_data, processed_options)
            
            # Handle email delivery if requested
            if processed_options['email_addresses']:
                self._send_email_report(output_file, processed_options)
            
            # Save configuration if requested
            if options['save_config']:
                self._save_configuration(options['save_config'], processed_options)
            
            # Display completion summary
            self._display_completion_summary(output_file, processed_options)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Report generation failed: {str(e)}')
            )
            if options['verbosity'] >= 2:
                import traceback
                self.stdout.write(traceback.format_exc())
            sys.exit(1)
    
    def _validate_options(self, options):
        """Validate command line options and combinations"""
        # Validate date formats
        for date_field in ['date_from', 'date_to', 'as_of_date']:
            if options[date_field]:
                try:
                    datetime.strptime(options[date_field], '%Y-%m-%d')
                except ValueError:
                    raise CommandError(f'Invalid date format for {date_field}. Use YYYY-MM-DD.')
        
        # Validate date ranges
        if options['date_from'] and options['date_to']:
            date_from = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
            date_to = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
            if date_from > date_to:
                raise CommandError('date_from cannot be later than date_to')
        
        # Validate aging periods
        if options['aging_periods']:
            try:
                periods = [int(p.strip()) for p in options['aging_periods'].split(',')]
                if not all(p > 0 for p in periods):
                    raise ValueError
            except ValueError:
                raise CommandError('Invalid aging periods. Use comma-separated positive integers.')
        
        # Validate min/max values
        if options['min_value'] and options['max_value']:
            if options['min_value'] > options['max_value']:
                raise CommandError('min_value cannot be greater than max_value')
    
    def _process_options(self, options):
        """Process and enhance options with additional data"""
        processed = options.copy()
        
        # Process date ranges
        if options['date_from']:
            processed['date_from_obj'] = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
        elif options['period']:
            processed['date_from_obj'] = timezone.now().date() - timedelta(days=options['period'])
        else:
            processed['date_from_obj'] = timezone.now().date() - timedelta(days=30)
        
        if options['date_to']:
            processed['date_to_obj'] = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
        else:
            processed['date_to_obj'] = timezone.now().date()
        
        if options['as_of_date']:
            processed['as_of_date_obj'] = datetime.strptime(options['as_of_date'], '%Y-%m-%d').date()
        else:
            processed['as_of_date_obj'] = timezone.now().date()
        
        # Process filter objects
        processed['category_obj'] = self._get_filter_object(Category, options['category'])
        processed['supplier_obj'] = self._get_filter_object(Supplier, options['supplier'])
        processed['location_obj'] = self._get_filter_object(Location, options['location'])
        
        # Process email addresses
        processed['email_addresses'] = []
        if options['email']:
            processed['email_addresses'] = [
                email.strip() for email in options['email'].split(',')
            ]
        
        # Process aging periods
        processed['aging_periods_list'] = [
            int(p.strip()) for p in options['aging_periods'].split(',')
        ]
        
        # Generate output filename if not provided
        if not options['output_file']:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            processed['output_file'] = f"stock_report_{options['report_type']}_{timestamp}.{options['format']}"
        else:
            processed['output_file'] = options['output_file']
        
        return processed
    
    def _get_filter_object(self, model, filter_value):
        """Get filter object by name or ID"""
        if not filter_value:
            return None
        
        try:
            # Try as ID first
            if filter_value.isdigit():
                return model.objects.get(id=int(filter_value))
            else:
                # Try as name
                return model.objects.get(name__iexact=filter_value)
        except model.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'{model.__name__} "{filter_value}" not found. Ignoring filter.')
            )
            return None
    
    def _display_configuration(self, options):
        """Display report generation configuration"""
        self.stdout.write(self.style.SUCCESS('=== Stock Report Generation Configuration ==='))
        self.stdout.write(f'Report Type: {options["report_type"].title()}')
        self.stdout.write(f'Output Format: {options["format"].upper()}')
        self.stdout.write(f'Output File: {options["output_file"]}')
        self.stdout.write(f'Date Range: {options["date_from_obj"]} to {options["date_to_obj"]}')
        
        # Show active filters
        filters = []
        if options['category_obj']:
            filters.append(f'Category: {options["category_obj"].name}')
        if options['supplier_obj']:
            filters.append(f'Supplier: {options["supplier_obj"].name}')
        if options['location_obj']:
            filters.append(f'Location: {options["location_obj"].name}')
        if options['sku_pattern']:
            filters.append(f'SKU Pattern: {options["sku_pattern"]}')
        
        if filters:
            self.stdout.write(f'Filters: {", ".join(filters)}')
        
        if options['email_addresses']:
            self.stdout.write(f'Email Recipients: {", ".join(options["email_addresses"])}')
        
        self.stdout.write('')
    
    def _generate_report(self, options):
        """Generate the requested report based on type"""
        report_type = options['report_type']
        
        self.stdout.write(f'Generating {report_type} report...')
        
        # Route to appropriate report generator
        if report_type == 'valuation':
            return self._generate_valuation_report(options)
        elif report_type == 'movement':
            return self._generate_movement_report(options)
        elif report_type == 'reorder':
            return self._generate_reorder_report(options)
        elif report_type == 'abc':
            return self._generate_abc_report(options)
        elif report_type == 'aging':
            return self._generate_aging_report(options)
        elif report_type == 'supplier':
            return self._generate_supplier_report(options)
        elif report_type == 'low-stock':
            return self._generate_low_stock_report(options)
        elif report_type == 'category':
            return self._generate_category_report(options)
        elif report_type == 'location':
            return self._generate_location_report(options)
        elif report_type == 'custom':
            return self._generate_custom_report(options)
        else:
            raise CommandError(f'Unknown report type: {report_type}')
    
    def _generate_valuation_report(self, options):
        """Generate inventory valuation report"""
        return generate_stock_valuation_report(
            location=options['location_obj'],
            category=options['category_obj'],
            as_of_date=options['as_of_date_obj']
        )
    
    def _generate_movement_report(self, options):
        """Generate stock movement analysis report"""
        # Build base query for stock movements
        movements = StockMovement.objects.filter(
            created_at__gte=options['date_from_obj'],
            created_at__lte=options['date_to_obj']
        ).select_related('product', 'created_by', 'from_location', 'to_location')
        
        # Apply filters
        if options['category_obj']:
            movements = movements.filter(product__category=options['category_obj'])
        if options['supplier_obj']:
            movements = movements.filter(product__supplier=options['supplier_obj'])
        if options['location_obj']:
            movements = movements.filter(
                Q(from_location=options['location_obj']) | 
                Q(to_location=options['location_obj'])
            )
        
        # Generate summary statistics
        movement_summary = movements.aggregate(
            total_movements=Count('id'),
            total_in=Sum('quantity', filter=Q(quantity__gt=0)),
            total_out=Sum('quantity', filter=Q(quantity__lt=0)),
            total_value=Sum('total_cost', filter=Q(total_cost__isnull=False))
        )
        
        # Movement breakdown by type
        movement_by_type = movements.values('movement_type').annotate(
            count=Count('id'),
            quantity=Sum('quantity'),
            value=Sum('total_cost')
        ).order_by('-count')
        
        # Top products by movement volume
        top_products = movements.values(
            'product__sku', 'product__name'
        ).annotate(
            total_movements=Count('id'),
            net_quantity=Sum('quantity'),
            total_value=Sum('total_cost')
        ).order_by('-total_movements')[:20]
        
        return {
            'report_type': 'Stock Movement Analysis',
            'period': f"{options['date_from_obj']} to {options['date_to_obj']}",
            'summary': movement_summary,
            'by_type': list(movement_by_type),
            'top_products': list(top_products),
            'movements': list(movements.values(
                'created_at', 'product__sku', 'product__name',
                'movement_type', 'quantity', 'reference',
                'from_location__name', 'to_location__name'
            )[:1000])  # Limit detailed movements
        }
    
    def _generate_reorder_report(self, options):
        """Generate reorder recommendations report"""
        from inventory.utils import calculate_reorder_recommendations
        
        recommendations = calculate_reorder_recommendations(
            category=options['category_obj'],
            supplier=options['supplier_obj']
        )
        
        # Group by priority
        by_priority = {}
        total_cost = Decimal('0.00')
        
        for rec in recommendations:
            priority = rec['priority']
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(rec)
            total_cost += rec['estimated_cost']
        
        return {
            'report_type': 'Reorder Recommendations',
            'generated_at': timezone.now(),
            'total_products': len(recommendations),
            'total_estimated_cost': total_cost,
            'by_priority': by_priority,
            'recommendations': recommendations
        }
    
    def _generate_abc_report(self, options):
        """Generate ABC analysis report"""
        return generate_abc_analysis(
            criteria=options['abc_criteria'],
            period_days=options['period']
        )
    
    def _generate_aging_report(self, options):
        """Generate stock aging analysis report"""
        products = self._get_filtered_products(options)
        aging_periods = options['aging_periods_list']
        
        # Calculate aging for each product
        aging_data = []
        current_date = timezone.now().date()
        
        for product in products:
            last_movement = StockMovement.objects.filter(
                product=product,
                movement_type__in=['sale', 'out']
            ).order_by('-created_at').first()
            
            if last_movement:
                days_since_movement = (current_date - last_movement.created_at.date()).days
            else:
                days_since_movement = 999  # Never moved
            
            # Determine aging category
            aging_category = 'Very Old'
            for period in sorted(aging_periods):
                if days_since_movement <= period:
                    aging_category = f'0-{period} days'
                    break
            
            stock_value = product.current_stock * product.cost_price
            
            aging_data.append({
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'current_stock': product.current_stock,
                'stock_value': stock_value,
                'days_since_movement': days_since_movement,
                'aging_category': aging_category,
                'last_movement_date': last_movement.created_at.date() if last_movement else None
            })
        
        # Summarize by aging category
        aging_summary = {}
        for item in aging_data:
            category = item['aging_category']
            if category not in aging_summary:
                aging_summary[category] = {
                    'product_count': 0,
                    'total_quantity': 0,
                    'total_value': Decimal('0.00')
                }
            
            aging_summary[category]['product_count'] += 1
            aging_summary[category]['total_quantity'] += item['current_stock']
            aging_summary[category]['total_value'] += item['stock_value']
        
        return {
            'report_type': 'Stock Aging Analysis',
            'aging_periods': aging_periods,
            'summary': aging_summary,
            'products': aging_data
        }
    
    def _generate_supplier_report(self, options):
        """Generate supplier performance analysis report"""
        suppliers = Supplier.objects.filter(is_active=True)
        
        if options['supplier_obj']:
            suppliers = suppliers.filter(id=options['supplier_obj'].id)
        
        supplier_data = []
        
        for supplier in suppliers:
            # Get products from this supplier
            products = Product.objects.filter(supplier=supplier, is_active=True)
            
            # Calculate metrics
            total_products = products.count()
            total_stock_value = sum(p.current_stock * p.cost_price for p in products)
            
            # Purchase orders in period
            pos_in_period = PurchaseOrder.objects.filter(
                supplier=supplier,
                order_date__gte=options['date_from_obj'],
                order_date__lte=options['date_to_obj']
            )
            
            po_metrics = pos_in_period.aggregate(
                total_pos=Count('id'),
                total_value=Sum('total_amount'),
                avg_lead_time=Avg('expected_delivery_date') - Avg('order_date')
            )
            
            # On-time delivery performance
            delivered_pos = pos_in_period.filter(status='received')
            on_time_deliveries = delivered_pos.filter(
                actual_delivery_date__lte=F('expected_delivery_date')
            ).count()
            
            delivery_performance = (
                (on_time_deliveries / delivered_pos.count() * 100) 
                if delivered_pos.count() > 0 else 0
            )
            
            supplier_data.append({
                'supplier_code': supplier.supplier_code,
                'name': supplier.name,
                'country': supplier.country,
                'total_products': total_products,
                'total_stock_value': total_stock_value,
                'purchase_orders': po_metrics['total_pos'] or 0,
                'purchase_value': po_metrics['total_value'] or Decimal('0.00'),
                'delivery_performance': round(delivery_performance, 1),
                'reliability_rating': supplier.reliability_rating,
                'average_lead_time': supplier.average_lead_time_days
            })
        
        return {
            'report_type': 'Supplier Performance Analysis',
            'period': f"{options['date_from_obj']} to {options['date_to_obj']}",
            'suppliers': supplier_data
        }
    
    def _generate_low_stock_report(self, options):
        """Generate low stock alert report"""
        products = self._get_filtered_products(options).filter(
            current_stock__lte=F('reorder_level')
        )
        
        low_stock_data = []
        critical_count = 0
        high_priority_count = 0
        
        for product in products:
            stock_ratio = product.current_stock / max(product.reorder_level, 1)
            
            if stock_ratio <= 0:
                priority = 'Critical'
                critical_count += 1
            elif stock_ratio <= 0.5:
                priority = 'High'
                high_priority_count += 1
            else:
                priority = 'Medium'
            
            low_stock_data.append({
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'supplier': product.supplier.name,
                'current_stock': product.current_stock,
                'reorder_level': product.reorder_level,
                'reorder_quantity': product.reorder_quantity,
                'priority': priority,
                'estimated_cost': product.reorder_quantity * product.cost_price,
                'lead_time_days': product.supplier_lead_time_days
            })
        
        return {
            'report_type': 'Low Stock Alert Report',
            'generated_at': timezone.now(),
            'total_products': len(low_stock_data),
            'critical_count': critical_count,
            'high_priority_count': high_priority_count,
            'products': low_stock_data
        }
    
    def _generate_category_report(self, options):
        """Generate category performance report"""
        categories = Category.objects.filter(is_active=True)
        
        if options['category_obj']:
            categories = categories.filter(id=options['category_obj'].id)
        
        category_data = []
        
        for category in categories:
            products = Product.objects.filter(category=category, is_active=True)
            
            # Calculate metrics
            total_products = products.count()
            total_stock_value = sum(p.current_stock * p.cost_price for p in products)
            total_selling_value = sum(p.current_stock * p.selling_price for p in products)
            
            # Movement analysis
            movements = StockMovement.objects.filter(
                product__category=category,
                created_at__gte=options['date_from_obj'],
                created_at__lte=options['date_to_obj']
            )
            
            movement_metrics = movements.aggregate(
                total_movements=Count('id'),
                total_out=Sum('quantity', filter=Q(quantity__lt=0)),
                total_revenue=Sum('total_cost', filter=Q(movement_type='sale'))
            )
            
            category_data.append({
                'name': category.name,
                'total_products': total_products,
                'stock_value': total_stock_value,
                'potential_revenue': total_selling_value,
                'movements': movement_metrics['total_movements'] or 0,
                'units_sold': abs(movement_metrics['total_out'] or 0),
                'revenue': movement_metrics['total_revenue'] or Decimal('0.00'),
                'avg_margin': category.default_markup_percentage
            })
        
        return {
            'report_type': 'Category Performance Analysis',
            'period': f"{options['date_from_obj']} to {options['date_to_obj']}",
            'categories': category_data
        }
    
    def _generate_location_report(self, options):
        """Generate location stock distribution report"""
        locations = Location.objects.filter(is_active=True)
        
        if options['location_obj']:
            locations = locations.filter(id=options['location_obj'].id)
        
        location_data = []
        
        for location in locations:
            stock_levels = StockLevel.objects.filter(location=location)
            
            # Calculate metrics
            total_products = stock_levels.filter(quantity__gt=0).count()
            total_quantity = stock_levels.aggregate(total=Sum('quantity'))['total'] or 0
            
            # Calculate value
            total_value = sum(
                sl.quantity * sl.product.cost_price 
                for sl in stock_levels.select_related('product')
            )
            
            # Capacity utilization
            capacity_usage = location.current_capacity_usage if location.max_capacity else 0
            
            location_data.append({
                'name': location.name,
                'location_type': location.get_location_type_display(),
                'total_products': total_products,
                'total_quantity': total_quantity,
                'total_value': total_value,
                'capacity_usage': capacity_usage,
                'max_capacity': location.max_capacity,
                'is_sellable': location.is_sellable
            })
        
        return {
            'report_type': 'Location Stock Distribution',
            'locations': location_data
        }
    
    def _generate_custom_report(self, options):
        """Generate custom report based on specified parameters"""
        # This would be implemented based on specific custom requirements
        # For now, return a comprehensive overview
        
        products = self._get_filtered_products(options)
        
        report_data = {
            'report_type': 'Custom Inventory Report',
            'filters_applied': self._get_filter_summary(options),
            'total_products': products.count(),
            'total_stock_value': calculate_stock_value(products),
            'products': []
        }
        
        # Add detailed product information
        for product in products[:options.get('limit', 1000)]:
            product_data = {
                'sku': product.sku,
                'name': product.name,
                'category': product.category.name,
                'supplier': product.supplier.name,
                'current_stock': product.current_stock,
                'stock_value': product.current_stock * product.cost_price,
                'selling_price': product.selling_price if options['include_costs'] else None,
                'profit_margin': product.profit_margin_percentage if options['include_costs'] else None
            }
            report_data['products'].append(product_data)
        
        return report_data
    
    def _get_filtered_products(self, options):
        """Get filtered product queryset based on options"""
        queryset = Product.objects.select_related('category', 'supplier')
        
        if not options['include_inactive']:
            queryset = queryset.filter(is_active=True)
        
        # Apply filters
        if options['category_obj']:
            queryset = queryset.filter(category=options['category_obj'])
        
        if options['supplier_obj']:
            queryset = queryset.filter(supplier=options['supplier_obj'])
        
        if options['sku_pattern']:
            pattern = options['sku_pattern'].replace('*', '%')
            queryset = queryset.extra(where=["sku LIKE %s"], params=[pattern])
        
        if options['min_value'] or options['max_value']:
            # Filter by stock value
            for product in queryset:
                stock_value = float(product.current_stock * product.cost_price)
                if options['min_value'] and stock_value < options['min_value']:
                    queryset = queryset.exclude(id=product.id)
                if options['max_value'] and stock_value > options['max_value']:
                    queryset = queryset.exclude(id=product.id)
        
        return queryset
    
    def _get_filter_summary(self, options):
        """Get summary of applied filters"""
        filters = []
        
        if options['category_obj']:
            filters.append(f"Category: {options['category_obj'].name}")
        if options['supplier_obj']:
            filters.append(f"Supplier: {options['supplier_obj'].name}")
        if options['location_obj']:
            filters.append(f"Location: {options['location_obj'].name}")
        if options['sku_pattern']:
            filters.append(f"SKU Pattern: {options['sku_pattern']}")
        if not options['include_inactive']:
            filters.append("Active products only")
        
        return filters
    
    def _generate_output(self, report_data, options):
        """Generate output file in requested format"""
        output_file = options['output_file']
        format_type = options['format']
        
        self.stdout.write(f'Generating {format_type.upper()} output...')
        
        if format_type == 'csv':
            self._generate_csv_output(report_data, output_file, options)
        elif format_type == 'json':
            self._generate_json_output(report_data, output_file, options)
        elif format_type == 'html':
            self._generate_html_output(report_data, output_file, options)
        elif format_type == 'pdf':
            self._generate_pdf_output(report_data, output_file, options)
        elif format_type == 'xlsx':
            self._generate_xlsx_output(report_data, output_file, options)
        else:
            raise CommandError(f'Unsupported output format: {format_type}')
        
        return output_file
    
    def _generate_csv_output(self, report_data, output_file, options):
        """Generate CSV output"""
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            # The CSV structure depends on the report type
            if options['report_type'] == 'valuation':
                self._write_valuation_csv(csvfile, report_data)
            elif options['report_type'] == 'movement':
                self._write_movement_csv(csvfile, report_data)
            elif options['report_type'] == 'reorder':
                self._write_reorder_csv(csvfile, report_data)
            elif options['report_type'] == 'low-stock':
                self._write_low_stock_csv(csvfile, report_data)
            else:
                # Generic CSV format
                self._write_generic_csv(csvfile, report_data)
    
    def _write_valuation_csv(self, csvfile, report_data):
        """Write valuation report to CSV"""
        writer = csv.writer(csvfile)
        
        # Header information
        writer.writerow(['Inventory Valuation Report'])
        writer.writerow(['As of Date:', report_data.get('as_of_date', 'Current')])
        writer.writerow(['Location:', report_data.get('location', 'All Locations')])
        writer.writerow(['Category:', report_data.get('category', 'All Categories')])
        writer.writerow([])
        
        # Summary
        writer.writerow(['Summary'])
        writer.writerow(['Total Products:', report_data.get('total_products', 0)])
        writer.writerow(['Total Quantity:', report_data.get('total_quantity', 0)])
        writer.writerow(['Total Value:', f"${report_data.get('total_value', 0):,.2f}"])
        writer.writerow([])
        
        # Category breakdown
        if 'categories' in report_data:
            writer.writerow(['Category Breakdown'])
            writer.writerow(['Category', 'Product Count', 'Total Quantity', 'Total Value'])
            for category in report_data['categories']:
                writer.writerow([
                    category['name'],
                    category['product_count'],
                    category['total_quantity'],
                    f"${category['total_value']:,.2f}"
                ])
            writer.writerow([])
        
        # Product details
        if 'products' in report_data:
            writer.writerow(['Product Details'])
            writer.writerow(['SKU', 'Name', 'Category', 'Supplier', 'Quantity', 'Cost Price', 'Total Value', 'Stock Status'])
            for product in report_data['products']:
                writer.writerow([
                    product['sku'],
                    product['name'],
                    product['category'],
                    product['supplier'],
                    product['quantity'],
                    f"${product['cost_price']:,.2f}",
                    f"${product['total_value']:,.2f}",
                    product['stock_status']
                ])
    
    def _write_movement_csv(self, csvfile, report_data):
        """Write movement report to CSV"""
        writer = csv.writer(csvfile)
        
        writer.writerow(['Stock Movement Report'])
        writer.writerow(['Period:', report_data['period']])
        writer.writerow([])
        
        # Summary
        writer.writerow(['Summary'])
        summary = report_data['summary']
        writer.writerow(['Total Movements:', summary['total_movements']])
        writer.writerow(['Total Stock In:', summary['total_in'] or 0])
        writer.writerow(['Total Stock Out:', abs(summary['total_out'] or 0)])
        writer.writerow(['Total Value:', f"${summary['total_value'] or 0:,.2f}"])
        writer.writerow([])
        
        # Movement details
        writer.writerow(['Movement Details'])
        writer.writerow(['Date', 'Product SKU', 'Product Name', 'Type', 'Quantity', 'Reference', 'From Location', 'To Location'])
        for movement in report_data['movements']:
            writer.writerow([
                movement['created_at'],
                movement['product__sku'],
                movement['product__name'],
                movement['movement_type'],
                movement['quantity'],
                movement['reference'],
                movement['from_location__name'] or '',
                movement['to_location__name'] or ''
            ])
    
    def _write_reorder_csv(self, csvfile, report_data):
        """Write reorder report to CSV"""
        writer = csv.writer(csvfile)
        
        writer.writerow(['Reorder Recommendations Report'])
        writer.writerow(['Generated at:', report_data['generated_at']])
        writer.writerow(['Total Products:', report_data['total_products']])
        writer.writerow(['Total Estimated Cost:', f"${report_data['total_estimated_cost']:,.2f}"])
        writer.writerow([])
        
        writer.writerow(['Reorder Details'])
        writer.writerow(['SKU', 'Product Name', 'Current Stock', 'Reorder Level', 'Recommended Qty', 'Priority', 'Supplier', 'Estimated Cost', 'Lead Time'])
        
        for rec in report_data['recommendations']:
            writer.writerow([
                rec['product'].sku,
                rec['product'].name,
                rec['current_stock'],
                rec['reorder_level'],
                rec['recommended_quantity'],
                rec['priority'],
                rec['supplier'].name,
                f"${rec['estimated_cost']:,.2f}",
                rec['lead_time_days']
            ])
    
    def _write_low_stock_csv(self, csvfile, report_data):
        """Write low stock report to CSV"""
        writer = csv.writer(csvfile)
        
        writer.writerow(['Low Stock Alert Report'])
        writer.writerow(['Generated at:', report_data['generated_at']])
        writer.writerow(['Total Products:', report_data['total_products']])
        writer.writerow(['Critical Count:', report_data['critical_count']])
        writer.writerow(['High Priority Count:', report_data['high_priority_count']])
        writer.writerow([])
        
        writer.writerow(['Product Details'])
        writer.writerow(['SKU', 'Name', 'Category', 'Supplier', 'Current Stock', 'Reorder Level', 'Priority', 'Reorder Qty', 'Estimated Cost'])
        
        for product in report_data['products']:
            writer.writerow([
                product['sku'],
                product['name'],
                product['category'],
                product['supplier'],
                product['current_stock'],
                product['reorder_level'],
                product['priority'],
                product['reorder_quantity'],
                f"${product['estimated_cost']:,.2f}"
            ])
    
    def _write_generic_csv(self, csvfile, report_data):
        """Write generic CSV format for other report types"""
        writer = csv.writer(csvfile)
        
        # Write report header
        writer.writerow([report_data.get('report_type', 'Stock Report')])
        if 'period' in report_data:
            writer.writerow(['Period:', report_data['period']])
        writer.writerow(['Generated at:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        # Write data based on available keys
        if 'products' in report_data and report_data['products']:
            # Product-based report
            first_product = report_data['products'][0]
            headers = list(first_product.keys())
            writer.writerow(headers)
            
            for product in report_data['products']:
                row = [product.get(header, '') for header in headers]
                writer.writerow(row)
        else:
            # Write JSON representation for complex data
            import json
            writer.writerow(['Report Data (JSON format):'])
            writer.writerow([json.dumps(report_data, indent=2, default=str)])
    
    def _generate_json_output(self, report_data, output_file, options):
        """Generate JSON output"""
        import json
        
        # Convert any non-serializable objects to strings
        def json_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            elif hasattr(obj, '__str__'):
                return str(obj)
            return obj
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(report_data, jsonfile, indent=2, default=json_serializer)
    
    def _generate_html_output(self, report_data, output_file, options):
        """Generate HTML output"""
        html_content = render_to_string('inventory/reports/report_template.html', {
            'report_data': report_data,
            'options': options,
            'generated_at': timezone.now()
        })
        
        with open(output_file, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html_content)
    
    def _generate_pdf_output(self, report_data, output_file, options):
        """Generate PDF output"""
        try:
            from weasyprint import HTML, CSS
            from django.template.loader import render_to_string
            
            # Generate HTML first
            html_content = render_to_string('inventory/reports/report_pdf_template.html', {
                'report_data': report_data,
                'options': options,
                'generated_at': timezone.now()
            })
            
            # Convert to PDF
            HTML(string=html_content).write_pdf(output_file)
            
        except ImportError:
            raise CommandError('WeasyPrint is required for PDF generation. Install with: pip install weasyprint')
    
    def _generate_xlsx_output(self, report_data, output_file, options):
        """Generate Excel output"""
        try:
            import pandas as pd
            
            # Create Excel writer
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Write different sheets based on report type
                if 'products' in report_data and report_data['products']:
                    df_products = pd.DataFrame(report_data['products'])
                    df_products.to_excel(writer, sheet_name='Products', index=False)
                
                if 'summary' in report_data:
                    df_summary = pd.DataFrame([report_data['summary']])
                    df_summary.to_excel(writer, sheet_name='Summary', index=False)
                
                if 'categories' in report_data:
                    df_categories = pd.DataFrame(report_data['categories'])
                    df_categories.to_excel(writer, sheet_name='Categories', index=False)
                
                # Add metadata sheet
                metadata = {
                    'Report Type': [report_data.get('report_type', 'Unknown')],
                    'Generated At': [timezone.now().strftime('%Y-%m-%d %H:%M:%S')],
                    'Period': [report_data.get('period', 'N/A')]
                }
                df_metadata = pd.DataFrame(metadata)
                df_metadata.to_excel(writer, sheet_name='Metadata', index=False)
                
        except ImportError:
            raise CommandError('pandas and openpyxl are required for Excel generation. Install with: pip install pandas openpyxl')
    
    def _send_email_report(self, output_file, options):
        """Send report via email"""
        self.stdout.write('Sending email report...')
        
        subject = options.get('email_subject') or f"Stock Report - {options['report_type'].title()}"
        
        message = f"""
        Attached is your requested stock report.
        
        Report Type: {options['report_type'].title()}
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        Format: {options['format'].upper()}
        
        This report was automatically generated by the BlitzTech Inventory Management System.
        """
        
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=options['email_addresses']
        )
        
        email.attach_file(output_file)
        email.send()
        
        self.stdout.write(
            self.style.SUCCESS(f'Report emailed to: {", ".join(options["email_addresses"])}')
        )
    
    def _save_configuration(self, config_file, options):
        """Save report configuration for reuse"""
        config = {
            'report_type': options['report_type'],
            'format': options['format'],
            'period': options['period'],
            'category': options['category'],
            'supplier': options['supplier'],
            'location': options['location'],
            'include_inactive': options['include_inactive'],
            'group_by': options['group_by'],
            'sort_by': options['sort_by']
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.stdout.write(f'Configuration saved to: {config_file}')
    
    def _load_configuration(self, config_file, options):
        """Load report configuration from file"""
        if not os.path.exists(config_file):
            raise CommandError(f'Configuration file not found: {config_file}')
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Merge with command line options (CLI takes precedence)
        for key, value in config.items():
            if key not in options or options[key] is None:
                options[key] = value
        
        return options
    
    def _display_completion_summary(self, output_file, options):
        """Display completion summary"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Report Generation Complete ==='))
        self.stdout.write(f'Report Type: {options["report_type"].title()}')
        self.stdout.write(f'Output File: {output_file}')
        self.stdout.write(f'Format: {options["format"].upper()}')
        
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            self.stdout.write(f'File Size: {file_size:,} bytes')
        
        if options['email_addresses']:
            self.stdout.write(f'Emailed to: {", ".join(options["email_addresses"])}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Report generated successfully!'))
