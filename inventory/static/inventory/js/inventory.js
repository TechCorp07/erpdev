/**
 * Inventory Management System - Core JavaScript Functions
 * 
 * This file provides the core functionality for the inventory management system,
 * including AJAX operations, form handling, search, and utility functions.
 * 
 * Dependencies: jQuery, Bootstrap 5, Chart.js (for reports)
 */

// Global inventory application object
window.InventoryApp = window.InventoryApp || {};

(function($) {
    'use strict';

    // =====================================
    // CONFIGURATION AND CONSTANTS
    // =====================================

    const CONFIG = {
        // API endpoints
        endpoints: {
            productSearch: '/inventory/api/search/',
            stockAdjust: '/inventory/api/adjust/',
            stockTransfer: '/inventory/api/transfer/',
            checkSku: '/inventory/api/check-sku/',
            checkBarcode: '/inventory/api/check-barcode/',
            quickStats: '/inventory/quick-stats/'
        },
        
        // Timing
        searchDelay: 300,
        notificationDuration: 5000,
        autoRefreshInterval: 300000, // 5 minutes
        
        // UI settings
        tablePageSize: 25,
        searchMinLength: 2,
        
        // Stock status colors
        stockColors: {
            'in_stock': '#10b981',
            'low_stock': '#f59e0b', 
            'out_of_stock': '#ef4444',
            'critical': '#dc2626'
        }
    };

    // =====================================
    // UTILITY FUNCTIONS
    // =====================================

    const Utils = {
        /**
         * Get CSRF token from cookies
         */
        getCsrfToken: function() {
            const name = 'csrftoken';
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },

        /**
         * Format currency values
         */
        formatCurrency: function(amount, currency = 'USD') {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 2
            }).format(amount);
        },

        /**
         * Format numbers with thousands separators
         */
        formatNumber: function(number) {
            return new Intl.NumberFormat('en-US').format(number);
        },

        /**
         * Format dates
         */
        formatDate: function(date, format = 'short') {
            const options = {
                short: { year: 'numeric', month: 'short', day: 'numeric' },
                long: { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' },
                time: { hour: '2-digit', minute: '2-digit' }
            };
            return new Intl.DateTimeFormat('en-US', options[format]).format(new Date(date));
        },

        /**
         * Debounce function calls
         */
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        /**
         * Show loading state on element
         */
        showLoading: function(element) {
            const $element = $(element);
            $element.addClass('inventory-loading').prop('disabled', true);
        },

        /**
         * Hide loading state
         */
        hideLoading: function(element) {
            const $element = $(element);
            $element.removeClass('inventory-loading').prop('disabled', false);
        },

        /**
         * Generate unique ID
         */
        generateId: function() {
            return 'inv_' + Math.random().toString(36).substr(2, 9);
        }
    };

    // =====================================
    // NOTIFICATION SYSTEM
    // =====================================

    const Notifications = {
        /**
         * Show notification toast
         */
        show: function(message, type = 'info', duration = CONFIG.notificationDuration) {
            const id = Utils.generateId();
            const iconMap = {
                success: 'check-circle',
                error: 'exclamation-triangle',
                warning: 'exclamation-circle',
                info: 'info-circle'
            };

            const toast = $(`
                <div class="inventory-toast" id="${id}">
                    <div class="toast-header">
                        <i class="bi bi-${iconMap[type]} text-${type} me-2"></i>
                        <strong class="me-auto">Inventory System</strong>
                        <small class="text-muted">Just now</small>
                        <button type="button" class="btn-close" onclick="Notifications.hide('${id}')"></button>
                    </div>
                    <div class="toast-body">
                        ${message}
                    </div>
                </div>
            `);

            $('body').append(toast);
            
            // Auto-hide after duration
            if (duration > 0) {
                setTimeout(() => this.hide(id), duration);
            }

            return id;
        },

        /**
         * Hide notification
         */
        hide: function(id) {
            $(`#${id}`).fadeOut(300, function() {
                $(this).remove();
            });
        },

        /**
         * Show success notification
         */
        success: function(message) {
            return this.show(message, 'success');
        },

        /**
         * Show error notification
         */
        error: function(message) {
            return this.show(message, 'error', 8000);
        },

        /**
         * Show warning notification
         */
        warning: function(message) {
            return this.show(message, 'warning');
        },

        /**
         * Show info notification
         */
        info: function(message) {
            return this.show(message, 'info');
        }
    };

    // =====================================
    // AJAX HELPER FUNCTIONS
    // =====================================

    const Ajax = {
        /**
         * Make AJAX request with common settings
         */
        request: function(options) {
            const defaults = {
                type: 'GET',
                dataType: 'json',
                headers: {
                    'X-CSRFToken': Utils.getCsrfToken()
                },
                error: function(xhr, status, error) {
                    console.error('AJAX Error:', error);
                    Notifications.error('An error occurred. Please try again.');
                }
            };

            return $.ajax($.extend({}, defaults, options));
        },

        /**
         * GET request
         */
        get: function(url, data = {}) {
            return this.request({
                url: url,
                type: 'GET',
                data: data
            });
        },

        /**
         * POST request
         */
        post: function(url, data = {}) {
            return this.request({
                url: url,
                type: 'POST',
                data: JSON.stringify(data),
                contentType: 'application/json'
            });
        }
    };

    // =====================================
    // PRODUCT SEARCH FUNCTIONALITY
    // =====================================

    const ProductSearch = {
        /**
         * Initialize product search
         */
        init: function() {
            this.bindEvents();
            this.setupAutocomplete();
        },

        /**
         * Bind search events
         */
        bindEvents: function() {
            $(document).on('input', '.product-search-input', 
                Utils.debounce(this.handleSearch.bind(this), CONFIG.searchDelay)
            );

            $(document).on('click', '.search-result-item', this.selectProduct.bind(this));
        },

        /**
         * Handle search input
         */
        handleSearch: function(event) {
            const $input = $(event.target);
            const query = $input.val().trim();
            const $results = $input.siblings('.search-results');

            if (query.length < CONFIG.searchMinLength) {
                $results.hide();
                return;
            }

            Utils.showLoading($input);

            Ajax.get(CONFIG.endpoints.productSearch, { q: query })
                .done((data) => {
                    this.displaySearchResults($results, data.results || []);
                })
                .fail(() => {
                    Notifications.error('Search failed. Please try again.');
                })
                .always(() => {
                    Utils.hideLoading($input);
                });
        },

        /**
         * Display search results
         */
        displaySearchResults: function($container, results) {
            if (results.length === 0) {
                $container.html('<div class="search-no-results">No products found</div>').show();
                return;
            }

            const html = results.map(product => `
                <div class="search-result-item" data-product-id="${product.id}">
                    <div class="result-main">
                        <div class="result-name">${product.name}</div>
                        <div class="result-sku">${product.sku}</div>
                    </div>
                    <div class="result-details">
                        <div class="result-stock ${this.getStockStatusClass(product.stock_status)}">
                            ${product.available_stock} in stock
                        </div>
                        <div class="result-price">${Utils.formatCurrency(product.selling_price)}</div>
                    </div>
                </div>
            `).join('');

            $container.html(html).show();
        },

        /**
         * Get stock status CSS class
         */
        getStockStatusClass: function(status) {
            const classMap = {
                'in_stock': 'text-success',
                'low_stock': 'text-warning',
                'out_of_stock': 'text-danger'
            };
            return classMap[status] || 'text-muted';
        },

        /**
         * Select a product from search results
         */
        selectProduct: function(event) {
            const $item = $(event.currentTarget);
            const productId = $item.data('product-id');
            const productName = $item.find('.result-name').text();
            
            // Trigger custom event
            $(document).trigger('product:selected', {
                id: productId,
                name: productName,
                element: $item
            });

            // Hide results
            $item.closest('.search-results').hide();
        },

        /**
         * Setup autocomplete for search inputs
         */
        setupAutocomplete: function() {
            // Add autocomplete structure to search inputs
            $('.product-search-input').each(function() {
                const $input = $(this);
                if (!$input.siblings('.search-results').length) {
                    $input.after('<div class="search-results"></div>');
                }
            });

            // Close results when clicking outside
            $(document).on('click', function(event) {
                if (!$(event.target).closest('.product-search-container').length) {
                    $('.search-results').hide();
                }
            });
        }
    };

    // =====================================
    // STOCK MANAGEMENT
    // =====================================

    const StockManager = {
        /**
         * Initialize stock management
         */
        init: function() {
            this.bindEvents();
        },

        /**
         * Bind stock management events
         */
        bindEvents: function() {
            $(document).on('click', '.quick-adjust-btn', this.quickAdjust.bind(this));
            $(document).on('submit', '.stock-adjustment-form', this.handleAdjustmentForm.bind(this));
            $(document).on('click', '.stock-level-indicator', this.showStockDetails.bind(this));
        },

        /**
         * Quick stock adjustment
         */
        quickAdjust: function(event) {
            event.preventDefault();
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            const adjustmentType = $btn.data('adjustment-type');
            const quantity = parseInt($btn.data('quantity')) || 1;

            this.adjustStock(productId, adjustmentType, quantity, 'Quick adjustment');
        },

        /**
         * Handle stock adjustment form submission
         */
        handleAdjustmentForm: function(event) {
            event.preventDefault();
            const $form = $(event.currentTarget);
            const formData = this.serializeFormData($form);

            Utils.showLoading($form.find('[type="submit"]'));

            Ajax.post(CONFIG.endpoints.stockAdjust, formData)
                .done((data) => {
                    if (data.success) {
                        Notifications.success('Stock adjusted successfully');
                        this.updateStockDisplay(data.product_id, data.new_stock);
                        $form[0].reset();
                    } else {
                        Notifications.error(data.error || 'Adjustment failed');
                    }
                })
                .always(() => {
                    Utils.hideLoading($form.find('[type="submit"]'));
                });
        },

        /**
         * Adjust stock via API
         */
        adjustStock: function(productId, adjustmentType, quantity, reason) {
            const data = {
                product_id: productId,
                adjustment_type: adjustmentType,
                quantity: quantity,
                reason: reason
            };

            return Ajax.post(CONFIG.endpoints.stockAdjust, data)
                .done((response) => {
                    if (response.success) {
                        Notifications.success(`Stock ${adjustmentType}ed successfully`);
                        this.updateStockDisplay(productId, response.new_stock);
                        
                        // Trigger stock update event
                        $(document).trigger('stock:updated', response);
                    } else {
                        Notifications.error(response.error);
                    }
                });
        },

        /**
         * Update stock display in UI
         */
        updateStockDisplay: function(productId, newStock) {
            $(`.stock-quantity[data-product-id="${productId}"]`).text(newStock);
            $(`.current-stock[data-product-id="${productId}"]`).text(newStock);
            
            // Update stock status indicators
            this.updateStockStatusIndicators(productId, newStock);
        },

        /**
         * Update stock status indicators
         */
        updateStockStatusIndicators: function(productId, currentStock) {
            const $indicators = $(`.stock-level-indicator[data-product-id="${productId}"]`);
            
            $indicators.each(function() {
                const $indicator = $(this);
                const reorderLevel = parseInt($indicator.data('reorder-level')) || 0;
                const maxLevel = parseInt($indicator.data('max-level')) || 100;
                
                let status, percentage;
                
                if (currentStock <= 0) {
                    status = 'out-stock';
                    percentage = 0;
                } else if (currentStock <= reorderLevel) {
                    status = 'low-stock';
                    percentage = (currentStock / reorderLevel) * 30; // 30% max for low stock
                } else {
                    status = 'in-stock';
                    percentage = Math.min((currentStock / maxLevel) * 100, 100);
                }
                
                $indicator.find('.stock-level-fill')
                    .removeClass('in-stock low-stock out-stock')
                    .addClass(status)
                    .css('width', `${percentage}%`);
            });
        },

        /**
         * Show stock details modal
         */
        showStockDetails: function(event) {
            const $indicator = $(event.currentTarget);
            const productId = $indicator.data('product-id');
            
            // This would typically open a modal with detailed stock information
            // For now, we'll just trigger an event
            $(document).trigger('stock:details:requested', { productId: productId });
        },

        /**
         * Serialize form data to object
         */
        serializeFormData: function($form) {
            const formData = {};
            $form.serializeArray().forEach(item => {
                formData[item.name] = item.value;
            });
            return formData;
        }
    };

    // =====================================
    // FORM VALIDATION AND ENHANCEMENT
    // =====================================

    const FormEnhancer = {
        /**
         * Initialize form enhancements
         */
        init: function() {
            this.setupValidation();
            this.setupSKUValidation();
            this.setupBarcodeValidation();
            this.setupNumberFormatting();
        },

        /**
         * Setup real-time form validation
         */
        setupValidation: function() {
            $(document).on('blur', '.form-control[required]', function() {
                const $field = $(this);
                const isValid = this.checkValidity();
                
                $field.toggleClass('is-valid', isValid)
                      .toggleClass('is-invalid', !isValid);
            });
        },

        /**
         * Setup SKU availability checking
         */
        setupSKUValidation: function() {
            $(document).on('blur', '.sku-input', 
                Utils.debounce(this.checkSKUAvailability.bind(this), 500)
            );
        },

        /**
         * Check SKU availability
         */
        checkSKUAvailability: function(event) {
            const $input = $(event.target);
            const sku = $input.val().trim();
            const productId = $input.data('product-id');

            if (!sku) return;

            Ajax.get(CONFIG.endpoints.checkSku, { sku: sku, product_id: productId })
                .done((data) => {
                    const $feedback = $input.siblings('.invalid-feedback');
                    
                    if (data.available) {
                        $input.removeClass('is-invalid').addClass('is-valid');
                        $feedback.text('');
                    } else {
                        $input.removeClass('is-valid').addClass('is-invalid');
                        $feedback.text('SKU already in use');
                    }
                });
        },

        /**
         * Setup barcode validation
         */
        setupBarcodeValidation: function() {
            $(document).on('blur', '.barcode-input',
                Utils.debounce(this.checkBarcodeAvailability.bind(this), 500)
            );
        },

        /**
         * Check barcode availability
         */
        checkBarcodeAvailability: function(event) {
            const $input = $(event.target);
            const barcode = $input.val().trim();
            const productId = $input.data('product-id');

            if (!barcode) return;

            Ajax.get(CONFIG.endpoints.checkBarcode, { barcode: barcode, product_id: productId })
                .done((data) => {
                    const $feedback = $input.siblings('.invalid-feedback');
                    
                    if (data.available) {
                        $input.removeClass('is-invalid').addClass('is-valid');
                        $feedback.text('');
                    } else {
                        $input.removeClass('is-valid').addClass('is-invalid');
                        $feedback.text('Barcode already in use');
                    }
                });
        },

        /**
         * Setup number formatting
         */
        setupNumberFormatting: function() {
            $(document).on('blur', '.currency-input', function() {
                const $input = $(this);
                const value = parseFloat($input.val());
                
                if (!isNaN(value)) {
                    $input.val(value.toFixed(2));
                }
            });

            $(document).on('input', '.number-input', function() {
                this.value = this.value.replace(/[^0-9]/g, '');
            });
        }
    };

    // =====================================
    // DASHBOARD FUNCTIONALITY
    // =====================================

    const Dashboard = {
        /**
         * Initialize dashboard
         */
        init: function() {
            this.updateQuickStats();
            this.setupAutoRefresh();
            this.setupChartToggles();
        },

        /**
         * Update quick stats
         */
        updateQuickStats: function() {
            Ajax.get(CONFIG.endpoints.quickStats)
                .done((data) => {
                    if (data.success) {
                        this.updateStatsDisplay(data.stats);
                    }
                })
                .fail(() => {
                    console.warn('Failed to update quick stats');
                });
        },

        /**
         * Update stats display
         */
        updateStatsDisplay: function(stats) {
            Object.keys(stats).forEach(key => {
                const $element = $(`[data-metric="${key}"]`);
                if ($element.length) {
                    let value = stats[key];
                    
                    if (key.includes('value') || key.includes('cost')) {
                        value = Utils.formatCurrency(value);
                    } else if (typeof value === 'number' && value > 999) {
                        value = Utils.formatNumber(value);
                    }
                    
                    $element.text(value);
                }
            });
        },

        /**
         * Setup auto-refresh for dashboard
         */
        setupAutoRefresh: function() {
            setInterval(() => {
                this.updateQuickStats();
            }, CONFIG.autoRefreshInterval);
        },

        /**
         * Setup chart view toggles
         */
        setupChartToggles: function() {
            $(document).on('change', 'input[name="chartType"]', function() {
                const chartType = this.value;
                const chartId = $(this).closest('.chart-container').find('canvas').attr('id');
                
                $(document).trigger('chart:toggle', {
                    chartId: chartId,
                    type: chartType
                });
            });
        }
    };

    // =====================================
    // TABLE ENHANCEMENT
    // =====================================

    const TableEnhancer = {
        /**
         * Initialize table enhancements
         */
        init: function() {
            this.setupSorting();
            this.setupPagination();
            this.setupBulkActions();
            this.setupRowActions();
        },

        /**
         * Setup table sorting
         */
        setupSorting: function() {
            $(document).on('click', '.sortable-header', function() {
                const $header = $(this);
                const $table = $header.closest('table');
                const columnIndex = $header.index();
                const currentSort = $header.data('sort') || 'asc';
                const newSort = currentSort === 'asc' ? 'desc' : 'asc';
                
                // Update header indicators
                $table.find('.sortable-header').removeClass('sort-asc sort-desc');
                $header.addClass(`sort-${newSort}`).data('sort', newSort);
                
                // Sort table rows
                this.sortTableByColumn($table, columnIndex, newSort);
            });
        },

        /**
         * Sort table by column
         */
        sortTableByColumn: function($table, columnIndex, direction) {
            const $tbody = $table.find('tbody');
            const rows = $tbody.find('tr').toArray();
            
            rows.sort((a, b) => {
                const aText = $(a).find('td').eq(columnIndex).text().trim();
                const bText = $(b).find('td').eq(columnIndex).text().trim();
                
                // Try to parse as numbers
                const aNum = parseFloat(aText.replace(/[^0-9.-]/g, ''));
                const bNum = parseFloat(bText.replace(/[^0-9.-]/g, ''));
                
                let comparison;
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    comparison = aNum - bNum;
                } else {
                    comparison = aText.localeCompare(bText);
                }
                
                return direction === 'asc' ? comparison : -comparison;
            });
            
            $tbody.empty().append(rows);
        },

        /**
         * Setup table pagination
         */
        setupPagination: function() {
            // This would handle client-side pagination if needed
            // For now, we rely on server-side pagination
        },

        /**
         * Setup bulk actions
         */
        setupBulkActions: function() {
            $(document).on('change', '.select-all-checkbox', function() {
                const isChecked = this.checked;
                const $table = $(this).closest('table');
                
                $table.find('.row-checkbox').prop('checked', isChecked);
                this.updateBulkActionButtons($table);
            });

            $(document).on('change', '.row-checkbox', function() {
                const $table = $(this).closest('table');
                this.updateBulkActionButtons($table);
            });
        },

        /**
         * Update bulk action button states
         */
        updateBulkActionButtons: function($table) {
            const $checkboxes = $table.find('.row-checkbox');
            const checkedCount = $checkboxes.filter(':checked').length;
            
            $('.bulk-action-btn').prop('disabled', checkedCount === 0);
            $('.selected-count').text(checkedCount);
        },

        /**
         * Setup row actions
         */
        setupRowActions: function() {
            $(document).on('click', '.row-action-btn', function(event) {
                event.stopPropagation();
                
                const action = $(this).data('action');
                const rowId = $(this).closest('tr').data('id');
                
                $(document).trigger('table:row:action', {
                    action: action,
                    rowId: rowId,
                    button: this
                });
            });
        }
    };

    // =====================================
    // KEYBOARD SHORTCUTS
    // =====================================

    const KeyboardShortcuts = {
        /**
         * Initialize keyboard shortcuts
         */
        init: function() {
            $(document).on('keydown', this.handleKeydown.bind(this));
        },

        /**
         * Handle keydown events
         */
        handleKeydown: function(event) {
            // Only process if not in input fields
            if ($(event.target).is('input, textarea, select')) {
                return;
            }

            const key = event.key.toLowerCase();
            const ctrl = event.ctrlKey || event.metaKey;

            if (ctrl) {
                switch (key) {
                    case 'k':
                        event.preventDefault();
                        this.openQuickSearch();
                        break;
                    case 'n':
                        event.preventDefault();
                        this.newProduct();
                        break;
                    case 's':
                        event.preventDefault();
                        this.quickStockAdjustment();
                        break;
                }
            }
        },

        /**
         * Open quick search
         */
        openQuickSearch: function() {
            const $modal = $('#quickSearchModal');
            if ($modal.length) {
                $modal.modal('show');
                setTimeout(() => {
                    $modal.find('input').focus();
                }, 300);
            }
        },

        /**
         * Navigate to new product page
         */
        newProduct: function() {
            window.location.href = '/inventory/products/create/';
        },

        /**
         * Open quick stock adjustment
         */
        quickStockAdjustment: function() {
            const $modal = $('#quickAdjustModal');
            if ($modal.length) {
                $modal.modal('show');
            }
        }
    };

    // =====================================
    // INITIALIZATION
    // =====================================

    // Initialize all modules when DOM is ready
    $(document).ready(function() {
        ProductSearch.init();
        StockManager.init();
        FormEnhancer.init();
        Dashboard.init();
        TableEnhancer.init();
        KeyboardShortcuts.init();

        // Global event handlers
        $(document).on('product:selected', function(event, data) {
            console.log('Product selected:', data);
        });

        $(document).on('stock:updated', function(event, data) {
            console.log('Stock updated:', data);
        });

        // Initialize tooltips
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }

        console.log('Inventory Management System initialized');
    });

    // Expose public API
    window.InventoryApp = $.extend(window.InventoryApp, {
        Utils: Utils,
        Notifications: Notifications,
        Ajax: Ajax,
        ProductSearch: ProductSearch,
        StockManager: StockManager,
        FormEnhancer: FormEnhancer,
        Dashboard: Dashboard,
        TableEnhancer: TableEnhancer,
        CONFIG: CONFIG
    });

})(jQuery);
