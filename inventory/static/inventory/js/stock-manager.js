/**
 * Stock Manager - Advanced Stock Operations
 * 
 * This file handles complex stock management operations including:
 * - Stock transfers between locations
 * - Bulk stock adjustments
 * - Stock movement tracking
 * - Inventory reconciliation
 * - Real-time stock monitoring
 */

(function($) {
    'use strict';

    // =====================================
    // STOCK MANAGER MODULE
    // =====================================

    const StockManager = {
        // Configuration
        config: {
            endpoints: {
                transfer: '/inventory/api/transfer/',
                bulkAdjust: '/inventory/api/bulk-adjust/',
                stockLevels: '/inventory/api/stock-levels/',
                movements: '/inventory/api/movements/',
                reconcile: '/inventory/api/reconcile/'
            },
            pollInterval: 30000, // 30 seconds
            batchSize: 50
        },

        // Active transfers and operations
        activeOperations: new Map(),
        
        // Real-time updates
        isPolling: false,

        /**
         * Initialize Stock Manager
         */
        init: function() {
            this.bindEvents();
            this.initializeModals();
            this.setupRealTimeUpdates();
            this.loadPendingOperations();
        },

        /**
         * Bind event handlers
         */
        bindEvents: function() {
            // Stock transfer events
            $(document).on('click', '.transfer-stock-btn', this.openTransferModal.bind(this));
            $(document).on('submit', '#stockTransferForm', this.handleStockTransfer.bind(this));
            
            // Bulk adjustment events
            $(document).on('click', '.bulk-adjust-btn', this.openBulkAdjustModal.bind(this));
            $(document).on('submit', '#bulkAdjustForm', this.handleBulkAdjust.bind(this));
            
            // Location change events
            $(document).on('change', '.location-selector', this.handleLocationChange.bind(this));
            
            // Stock level monitoring
            $(document).on('click', '.monitor-stock-btn', this.toggleStockMonitoring.bind(this));
            
            // Quick actions
            $(document).on('click', '.quick-transfer-btn', this.quickTransfer.bind(this));
            $(document).on('click', '.quick-adjust-btn', this.quickAdjust.bind(this));
            
            // Reconciliation
            $(document).on('click', '.reconcile-btn', this.startReconciliation.bind(this));
            
            // Movement tracking
            $(document).on('click', '.view-movements-btn', this.viewMovements.bind(this));
        },

        /**
         * Initialize modals and UI components
         */
        initializeModals: function() {
            // Create stock transfer modal if it doesn't exist
            if (!$('#stockTransferModal').length) {
                this.createTransferModal();
            }
            
            // Create bulk adjustment modal
            if (!$('#bulkAdjustModal').length) {
                this.createBulkAdjustModal();
            }
            
            // Create movements modal
            if (!$('#movementsModal').length) {
                this.createMovementsModal();
            }
        },

        /**
         * Create stock transfer modal
         */
        createTransferModal: function() {
            const modalHtml = `
                <div class="modal fade" id="stockTransferModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-arrow-left-right me-2"></i>Stock Transfer
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <form id="stockTransferForm">
                                <div class="modal-body">
                                    <div class="row g-3">
                                        <div class="col-12">
                                            <label class="form-label">Product</label>
                                            <select class="form-select" name="product_id" required>
                                                <option value="">Select Product...</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">From Location</label>
                                            <select class="form-select" name="from_location" required>
                                                <option value="">Select Location...</option>
                                            </select>
                                            <div class="available-stock mt-1 small text-muted"></div>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">To Location</label>
                                            <select class="form-select" name="to_location" required>
                                                <option value="">Select Location...</option>
                                            </select>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Quantity to Transfer</label>
                                            <input type="number" class="form-control" name="quantity" min="1" required>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Transfer Reference</label>
                                            <input type="text" class="form-control" name="reference" 
                                                   placeholder="e.g., TR-001">
                                        </div>
                                        <div class="col-12">
                                            <label class="form-label">Notes</label>
                                            <textarea class="form-control" name="notes" rows="3" 
                                                      placeholder="Optional transfer notes..."></textarea>
                                        </div>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                        Cancel
                                    </button>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="bi bi-arrow-left-right me-1"></i>Transfer Stock
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            `;
            $('body').append(modalHtml);
            this.loadLocationsAndProducts();
        },

        /**
         * Create bulk adjustment modal
         */
        createBulkAdjustModal: function() {
            const modalHtml = `
                <div class="modal fade" id="bulkAdjustModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-gear me-2"></i>Bulk Stock Adjustment
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <form id="bulkAdjustForm">
                                <div class="modal-body">
                                    <div class="row mb-3">
                                        <div class="col-md-4">
                                            <label class="form-label">Adjustment Type</label>
                                            <select class="form-select" name="adjustment_type" required>
                                                <option value="set">Set to Specific Amount</option>
                                                <option value="add">Add to Current Stock</option>
                                                <option value="subtract">Subtract from Current Stock</option>
                                            </select>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Location</label>
                                            <select class="form-select" name="location">
                                                <option value="">All Locations</option>
                                            </select>
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Reason</label>
                                            <input type="text" class="form-control" name="reason" 
                                                   placeholder="Adjustment reason" required>
                                        </div>
                                    </div>
                                    
                                    <div class="table-responsive">
                                        <table class="table table-sm">
                                            <thead>
                                                <tr>
                                                    <th width="40">
                                                        <input type="checkbox" class="form-check-input select-all">
                                                    </th>
                                                    <th>Product</th>
                                                    <th>SKU</th>
                                                    <th class="text-end">Current Stock</th>
                                                    <th class="text-end">Adjustment</th>
                                                    <th class="text-end">New Stock</th>
                                                </tr>
                                            </thead>
                                            <tbody id="bulkAdjustItems">
                                                <!-- Items will be loaded here -->
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <div class="me-auto">
                                        <span class="selected-count">0</span> items selected
                                    </div>
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                        Cancel
                                    </button>
                                    <button type="submit" class="btn btn-warning" disabled>
                                        <i class="bi bi-gear me-1"></i>Apply Adjustments
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            `;
            $('body').append(modalHtml);
        },

        /**
         * Create movements modal
         */
        createMovementsModal: function() {
            const modalHtml = `
                <div class="modal fade" id="movementsModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-clock-history me-2"></i>Stock Movement History
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row mb-3">
                                    <div class="col-md-4">
                                        <input type="date" class="form-control" id="movementsFromDate" 
                                               placeholder="From Date">
                                    </div>
                                    <div class="col-md-4">
                                        <input type="date" class="form-control" id="movementsToDate" 
                                               placeholder="To Date">
                                    </div>
                                    <div class="col-md-4">
                                        <button type="button" class="btn btn-primary" id="filterMovements">
                                            <i class="bi bi-funnel me-1"></i>Filter
                                        </button>
                                    </div>
                                </div>
                                
                                <div id="movementsContainer">
                                    <!-- Movement history will be loaded here -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            $('body').append(modalHtml);
        },

        /**
         * Open stock transfer modal
         */
        openTransferModal: function(event) {
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            
            const $modal = $('#stockTransferModal');
            
            // Pre-select product if provided
            if (productId) {
                $modal.find('[name="product_id"]').val(productId).trigger('change');
            }
            
            $modal.modal('show');
        },

        /**
         * Handle stock transfer form submission
         */
        handleStockTransfer: function(event) {
            event.preventDefault();
            
            const $form = $(event.currentTarget);
            const formData = this.serializeFormData($form);
            const $submitBtn = $form.find('[type="submit"]');
            
            // Validate transfer
            if (!this.validateTransfer(formData)) {
                return;
            }
            
            window.InventoryApp.Utils.showLoading($submitBtn);
            
            window.InventoryApp.Ajax.post(this.config.endpoints.transfer, formData)
                .done((response) => {
                    if (response.success) {
                        window.InventoryApp.Notifications.success('Stock transferred successfully');
                        $('#stockTransferModal').modal('hide');
                        $form[0].reset();
                        
                        // Update UI
                        this.updateStockDisplays(response.movements);
                        
                        // Track operation
                        this.trackOperation('transfer', response.operation_id);
                    } else {
                        window.InventoryApp.Notifications.error(response.error);
                    }
                })
                .always(() => {
                    window.InventoryApp.Utils.hideLoading($submitBtn);
                });
        },

        /**
         * Validate transfer data
         */
        validateTransfer: function(data) {
            if (data.from_location === data.to_location) {
                window.InventoryApp.Notifications.error('From and To locations must be different');
                return false;
            }
            
            if (parseInt(data.quantity) <= 0) {
                window.InventoryApp.Notifications.error('Quantity must be greater than 0');
                return false;
            }
            
            return true;
        },

        /**
         * Quick transfer between locations
         */
        quickTransfer: function(event) {
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            const fromLocation = $btn.data('from-location');
            const toLocation = $btn.data('to-location');
            const quantity = parseInt($btn.data('quantity')) || 1;
            
            const transferData = {
                product_id: productId,
                from_location: fromLocation,
                to_location: toLocation,
                quantity: quantity,
                reference: 'Quick Transfer',
                notes: 'Quick transfer via UI'
            };
            
            if (confirm(`Transfer ${quantity} units from ${fromLocation} to ${toLocation}?`)) {
                this.executeTransfer(transferData);
            }
        },

        /**
         * Execute transfer operation
         */
        executeTransfer: function(transferData) {
            return window.InventoryApp.Ajax.post(this.config.endpoints.transfer, transferData)
                .done((response) => {
                    if (response.success) {
                        window.InventoryApp.Notifications.success('Transfer completed');
                        this.updateStockDisplays(response.movements);
                    } else {
                        window.InventoryApp.Notifications.error(response.error);
                    }
                });
        },

        /**
         * Quick stock adjustment
         */
        quickAdjust: function(event) {
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            const adjustmentType = $btn.data('adjustment-type');
            const quantity = parseInt($btn.data('quantity')) || 1;
            const reason = $btn.data('reason') || 'Quick adjustment';
            
            const adjustmentData = {
                product_id: productId,
                adjustment_type: adjustmentType,
                quantity: quantity,
                reason: reason
            };
            
            this.executeAdjustment(adjustmentData);
        },

        /**
         * Execute adjustment operation
         */
        executeAdjustment: function(adjustmentData) {
            return window.InventoryApp.Ajax.post('/inventory/api/adjust/', adjustmentData)
                .done((response) => {
                    if (response.success) {
                        window.InventoryApp.Notifications.success('Stock adjusted');
                        this.updateStockDisplay(response.product_id, response.new_stock);
                    } else {
                        window.InventoryApp.Notifications.error(response.error);
                    }
                });
        },

        /**
         * Open bulk adjustment modal
         */
        openBulkAdjustModal: function(event) {
            const $modal = $('#bulkAdjustModal');
            
            // Load products for bulk adjustment
            this.loadProductsForBulkAdjust();
            
            $modal.modal('show');
        },

        /**
         * Load products for bulk adjustment
         */
        loadProductsForBulkAdjust: function() {
            const $container = $('#bulkAdjustItems');
            
            $container.html('<tr><td colspan="6" class="text-center">Loading products...</td></tr>');
            
            window.InventoryApp.Ajax.get('/inventory/api/products/', { for_bulk_adjust: true })
                .done((response) => {
                    if (response.success) {
                        this.renderBulkAdjustItems(response.products);
                    } else {
                        $container.html('<tr><td colspan="6" class="text-center text-danger">Failed to load products</td></tr>');
                    }
                });
        },

        /**
         * Render bulk adjustment items
         */
        renderBulkAdjustItems: function(products) {
            const $container = $('#bulkAdjustItems');
            
            const html = products.map(product => `
                <tr data-product-id="${product.id}">
                    <td>
                        <input type="checkbox" class="form-check-input product-checkbox" value="${product.id}">
                    </td>
                    <td>${product.name}</td>
                    <td><code>${product.sku}</code></td>
                    <td class="text-end current-stock">${product.current_stock}</td>
                    <td class="text-end">
                        <input type="number" class="form-control form-control-sm adjustment-input" 
                               data-product-id="${product.id}" min="0" style="width: 80px;">
                    </td>
                    <td class="text-end new-stock">-</td>
                </tr>
            `).join('');
            
            $container.html(html);
            
            // Bind adjustment input events
            $container.find('.adjustment-input').on('input', this.calculateNewStock.bind(this));
            $container.find('.product-checkbox').on('change', this.updateBulkAdjustSelection.bind(this));
            
            // Bind select all
            $('.select-all').on('change', this.toggleSelectAll.bind(this));
        },

        /**
         * Calculate new stock values
         */
        calculateNewStock: function(event) {
            const $input = $(event.currentTarget);
            const $row = $input.closest('tr');
            const currentStock = parseInt($row.find('.current-stock').text());
            const adjustmentValue = parseInt($input.val()) || 0;
            const adjustmentType = $('[name="adjustment_type"]').val();
            
            let newStock;
            
            switch (adjustmentType) {
                case 'set':
                    newStock = adjustmentValue;
                    break;
                case 'add':
                    newStock = currentStock + adjustmentValue;
                    break;
                case 'subtract':
                    newStock = Math.max(0, currentStock - adjustmentValue);
                    break;
                default:
                    newStock = currentStock;
            }
            
            $row.find('.new-stock').text(newStock);
            
            // Highlight changes
            if (newStock !== currentStock) {
                $row.addClass('table-warning');
            } else {
                $row.removeClass('table-warning');
            }
        },

        /**
         * Update bulk adjustment selection
         */
        updateBulkAdjustSelection: function() {
            const selectedCount = $('.product-checkbox:checked').length;
            $('.selected-count').text(selectedCount);
            $('#bulkAdjustForm [type="submit"]').prop('disabled', selectedCount === 0);
        },

        /**
         * Toggle select all products
         */
        toggleSelectAll: function(event) {
            const isChecked = event.target.checked;
            $('.product-checkbox').prop('checked', isChecked);
            this.updateBulkAdjustSelection();
        },

        /**
         * Handle bulk adjustment form submission
         */
        handleBulkAdjust: function(event) {
            event.preventDefault();
            
            const $form = $(event.currentTarget);
            const adjustmentType = $form.find('[name="adjustment_type"]').val();
            const location = $form.find('[name="location"]').val();
            const reason = $form.find('[name="reason"]').val();
            
            // Collect selected products with adjustments
            const adjustments = [];
            $('.product-checkbox:checked').each(function() {
                const $checkbox = $(this);
                const $row = $checkbox.closest('tr');
                const productId = $checkbox.val();
                const adjustmentValue = parseInt($row.find('.adjustment-input').val()) || 0;
                
                if (adjustmentValue > 0 || adjustmentType === 'set') {
                    adjustments.push({
                        product_id: productId,
                        adjustment_type: adjustmentType,
                        quantity: adjustmentValue,
                        location: location,
                        reason: reason
                    });
                }
            });
            
            if (adjustments.length === 0) {
                window.InventoryApp.Notifications.warning('No adjustments to apply');
                return;
            }
            
            if (!confirm(`Apply ${adjustments.length} stock adjustments?`)) {
                return;
            }
            
            const $submitBtn = $form.find('[type="submit"]');
            window.InventoryApp.Utils.showLoading($submitBtn);
            
            window.InventoryApp.Ajax.post(this.config.endpoints.bulkAdjust, { adjustments })
                .done((response) => {
                    if (response.success) {
                        window.InventoryApp.Notifications.success(`${response.updated_count} products updated`);
                        $('#bulkAdjustModal').modal('hide');
                        
                        // Refresh current page or update displays
                        location.reload();
                    } else {
                        window.InventoryApp.Notifications.error(response.error);
                    }
                })
                .always(() => {
                    window.InventoryApp.Utils.hideLoading($submitBtn);
                });
        },

        /**
         * View stock movements
         */
        viewMovements: function(event) {
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            
            const $modal = $('#movementsModal');
            $modal.data('product-id', productId).modal('show');
            
            this.loadMovements(productId);
        },

        /**
         * Load stock movements
         */
        loadMovements: function(productId, filters = {}) {
            const $container = $('#movementsContainer');
            
            $container.html('<div class="text-center py-4"><div class="spinner-border"></div></div>');
            
            const params = { product_id: productId, ...filters };
            
            window.InventoryApp.Ajax.get(this.config.endpoints.movements, params)
                .done((response) => {
                    if (response.success) {
                        this.renderMovements(response.movements);
                    } else {
                        $container.html('<div class="alert alert-danger">Failed to load movements</div>');
                    }
                });
        },

        /**
         * Render stock movements
         */
        renderMovements: function(movements) {
            const $container = $('#movementsContainer');
            
            if (movements.length === 0) {
                $container.html('<div class="text-center text-muted py-4">No movements found</div>');
                return;
            }
            
            const html = `
                <div class="table-responsive">
                    <table class="table table-sm table-hover">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Type</th>
                                <th class="text-end">Quantity</th>
                                <th>From</th>
                                <th>To</th>
                                <th>Reference</th>
                                <th>User</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${movements.map(movement => `
                                <tr>
                                    <td>${window.InventoryApp.Utils.formatDate(movement.created_at, 'long')}</td>
                                    <td>
                                        <span class="badge bg-${this.getMovementTypeClass(movement.movement_type)}">
                                            ${movement.movement_type_display}
                                        </span>
                                    </td>
                                    <td class="text-end">
                                        <span class="${movement.quantity > 0 ? 'text-success' : 'text-danger'}">
                                            ${movement.quantity > 0 ? '+' : ''}${movement.quantity}
                                        </span>
                                    </td>
                                    <td>${movement.from_location || '-'}</td>
                                    <td>${movement.to_location || '-'}</td>
                                    <td>${movement.reference}</td>
                                    <td>${movement.created_by || 'System'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            
            $container.html(html);
        },

        /**
         * Get movement type CSS class
         */
        getMovementTypeClass: function(type) {
            const classMap = {
                'in': 'success',
                'out': 'danger',
                'transfer': 'info',
                'adjustment': 'warning',
                'sale': 'primary',
                'purchase': 'success'
            };
            return classMap[type] || 'secondary';
        },

        /**
         * Setup real-time stock updates
         */
        setupRealTimeUpdates: function() {
            // Start polling for stock updates
            this.startPolling();
            
            // Listen for visibility changes to optimize polling
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this.stopPolling();
                } else {
                    this.startPolling();
                }
            });
        },

        /**
         * Start polling for updates
         */
        startPolling: function() {
            if (this.isPolling) return;
            
            this.isPolling = true;
            this.pollTimer = setInterval(() => {
                this.pollStockUpdates();
            }, this.config.pollInterval);
        },

        /**
         * Stop polling
         */
        stopPolling: function() {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
                this.pollTimer = null;
            }
            this.isPolling = false;
        },

        /**
         * Poll for stock updates
         */
        pollStockUpdates: function() {
            // Only poll if there are stock displays on the page
            if ($('.stock-quantity, .current-stock').length === 0) {
                return;
            }
            
            window.InventoryApp.Ajax.get(this.config.endpoints.stockLevels)
                .done((response) => {
                    if (response.success) {
                        this.processStockUpdates(response.updates);
                    }
                })
                .fail(() => {
                    // Silently fail polling requests
                });
        },

        /**
         * Process stock updates
         */
        processStockUpdates: function(updates) {
            updates.forEach(update => {
                this.updateStockDisplay(update.product_id, update.current_stock);
                
                // Show notification for significant changes
                if (Math.abs(update.change) >= 10) {
                    const changeText = update.change > 0 ? `+${update.change}` : update.change.toString();
                    window.InventoryApp.Notifications.info(
                        `Stock updated: ${update.product_name} (${changeText})`
                    );
                }
            });
        },

        /**
         * Update stock display in UI
         */
        updateStockDisplay: function(productId, newStock) {
            // Update stock quantity displays
            $(`.stock-quantity[data-product-id="${productId}"]`).text(newStock);
            $(`.current-stock[data-product-id="${productId}"]`).text(newStock);
            
            // Update stock level indicators
            this.updateStockLevelIndicators(productId, newStock);
            
            // Trigger update event
            $(document).trigger('stock:display:updated', {
                productId: productId,
                newStock: newStock
            });
        },

        /**
         * Update stock level indicators
         */
        updateStockLevelIndicators: function(productId, currentStock) {
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
                    percentage = (currentStock / reorderLevel) * 30;
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
         * Update multiple stock displays
         */
        updateStockDisplays: function(movements) {
            movements.forEach(movement => {
                // Update stock displays based on movement data
                if (movement.product_id && movement.new_stock !== undefined) {
                    this.updateStockDisplay(movement.product_id, movement.new_stock);
                }
            });
        },

        /**
         * Track operation for monitoring
         */
        trackOperation: function(type, operationId) {
            this.activeOperations.set(operationId, {
                type: type,
                startTime: Date.now(),
                status: 'active'
            });
        },

        /**
         * Load locations and products for modals
         */
        loadLocationsAndProducts: function() {
            // Load locations
            window.InventoryApp.Ajax.get('/inventory/api/locations/')
                .done((response) => {
                    if (response.success) {
                        const options = response.locations.map(loc => 
                            `<option value="${loc.id}">${loc.name}</option>`
                        ).join('');
                        
                        $('#stockTransferModal [name="from_location"], #stockTransferModal [name="to_location"]')
                            .append(options);
                        $('#bulkAdjustModal [name="location"]').append(options);
                    }
                });
                
            // Load products
            window.InventoryApp.Ajax.get('/inventory/api/products/')
                .done((response) => {
                    if (response.success) {
                        const options = response.products.map(product => 
                            `<option value="${product.id}">${product.name} (${product.sku})</option>`
                        ).join('');
                        
                        $('#stockTransferModal [name="product_id"]').append(options);
                    }
                });
        },

        /**
         * Load pending operations
         */
        loadPendingOperations: function() {
            // This would load any pending operations from the server
            // For now, we'll just initialize an empty state
            console.log('Stock Manager initialized');
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
        },

        /**
         * Handle location change
         */
        handleLocationChange: function(event) {
            const $select = $(event.currentTarget);
            const locationId = $select.val();
            const productId = $select.data('product-id');
            
            if (productId && locationId) {
                this.updateAvailableStock(productId, locationId);
            }
        },

        /**
         * Update available stock display
         */
        updateAvailableStock: function(productId, locationId) {
            window.InventoryApp.Ajax.get('/inventory/api/stock-level/', {
                product_id: productId,
                location_id: locationId
            })
            .done((response) => {
                if (response.success) {
                    $('.available-stock').text(`Available: ${response.available_quantity}`);
                }
            });
        }
    };

    // Initialize when DOM is ready
    $(document).ready(function() {
        StockManager.init();
    });

    // Expose to global scope
    window.InventoryApp = window.InventoryApp || {};
    window.InventoryApp.StockManager = StockManager;

})(jQuery);
