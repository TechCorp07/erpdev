/**
 * Inventory Bulk Operations Manager
 * 
 * This module handles all bulk operations for inventory management including:
 * - Bulk product updates (prices, categories, suppliers)
 * - Bulk stock adjustments across multiple products
 * - Bulk import/export operations with progress tracking
 * - Bulk activation/deactivation of products
 * - Mass assignment of categories, suppliers, or other attributes
 * 
 * The system provides real-time progress feedback, comprehensive error handling,
 * and integrates with the existing permission system to ensure secure operations.
 */

class BulkOperationsManager {
    constructor() {
        this.selectedItems = new Set();
        this.operationInProgress = false;
        this.progressModal = null;
        this.currentOperation = null;
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    /**
     * Initialize bulk operations functionality
     * Sets up event listeners and UI components
     */
    init() {
        this.setupEventListeners();
        this.createProgressModal();
        this.setupSelectionHandlers();
        this.initializeToolbar();
        
        console.log('Bulk Operations Manager initialized');
    }

    /**
     * Set up main event listeners for bulk operations
     */
    setupEventListeners() {
        // Bulk action buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-bulk-action]')) {
                e.preventDefault();
                const action = e.target.dataset.bulkAction;
                this.handleBulkAction(action, e.target);
            }
        });

        // Select all/none functionality
        document.addEventListener('change', (e) => {
            if (e.target.matches('#selectAll')) {
                this.toggleSelectAll(e.target.checked);
            } else if (e.target.matches('.item-checkbox')) {
                this.handleItemSelection(e.target);
            }
        });

        // Keyboard shortcuts for bulk operations
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'a':
                        if (e.target.closest('.inventory-table-container')) {
                            e.preventDefault();
                            this.selectAllVisible();
                        }
                        break;
                    case 'u':
                        if (this.selectedItems.size > 0) {
                            e.preventDefault();
                            this.showBulkUpdateModal();
                        }
                        break;
                }
            }
        });
    }

    /**
     * Create modal for showing bulk operation progress
     */
    createProgressModal() {
        const modalHtml = `
            <div class="modal fade" id="bulkProgressModal" tabindex="-1" data-bs-backdrop="static">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="bi bi-gear-fill me-2"></i>
                                <span id="progressTitle">Processing Bulk Operation</span>
                            </h5>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Overall Progress</label>
                                <div class="progress" style="height: 20px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         id="overallProgress" 
                                         role="progressbar" 
                                         style="width: 0%"></div>
                                </div>
                                <div class="text-muted small mt-1">
                                    <span id="progressText">Preparing operation...</span>
                                    <span class="float-end" id="progressCount">0 / 0</span>
                                </div>
                            </div>
                            
                            <div class="card">
                                <div class="card-header d-flex justify-content-between">
                                    <span>Operation Details</span>
                                    <button type="button" class="btn-close" data-bs-toggle="collapse" 
                                            data-bs-target="#operationDetails"></button>
                                </div>
                                <div class="collapse show" id="operationDetails">
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <strong>Items to Process:</strong>
                                                <span id="itemsCount" class="badge bg-primary ms-2">0</span>
                                            </div>
                                            <div class="col-md-6">
                                                <strong>Success:</strong>
                                                <span id="successCount" class="badge bg-success ms-2">0</span>
                                                <strong class="ms-3">Errors:</strong>
                                                <span id="errorCount" class="badge bg-danger ms-2">0</span>
                                            </div>
                                        </div>
                                        
                                        <div class="mt-3">
                                            <label class="form-label">Current Item:</label>
                                            <div class="text-monospace small bg-light p-2 rounded" id="currentItem">
                                                Ready to start...
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Error Log -->
                            <div class="mt-3" id="errorLogContainer" style="display: none;">
                                <label class="form-label text-danger">
                                    <i class="bi bi-exclamation-triangle me-1"></i>Errors Encountered:
                                </label>
                                <div class="alert alert-danger" style="max-height: 200px; overflow-y: auto;">
                                    <ul id="errorLog" class="mb-0 small"></ul>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" id="cancelOperation">
                                <i class="bi bi-x-circle me-1"></i>Cancel
                            </button>
                            <button type="button" class="btn btn-primary" id="closeProgress" style="display: none;">
                                <i class="bi bi-check-circle me-1"></i>Close
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.progressModal = new bootstrap.Modal(document.getElementById('bulkProgressModal'));
        
        // Setup cancel button
        document.getElementById('cancelOperation').addEventListener('click', () => {
            this.cancelCurrentOperation();
        });
        
        document.getElementById('closeProgress').addEventListener('click', () => {
            this.progressModal.hide();
            this.resetProgress();
        });
    }

    /**
     * Setup selection handlers and checkbox management
     */
    setupSelectionHandlers() {
        // Update selection toolbar when items are selected/deselected
        this.updateSelectionToolbar();
    }

    /**
     * Initialize the bulk operations toolbar
     */
    initializeToolbar() {
        const toolbar = document.querySelector('.bulk-actions-toolbar');
        if (!toolbar) {
            this.createBulkToolbar();
        }
    }

    /**
     * Create bulk operations toolbar if it doesn't exist
     */
    createBulkToolbar() {
        const container = document.querySelector('.inventory-table-container');
        if (!container) return;

        const toolbarHtml = `
            <div class="bulk-actions-toolbar bg-light border rounded p-3 mb-3" style="display: none;">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <span class="text-muted">
                            <i class="bi bi-check-square me-1"></i>
                            <span id="selectedCount">0</span> items selected
                        </span>
                        <button type="button" class="btn btn-link btn-sm p-0 ms-2" 
                                onclick="bulkOps.clearSelection()">
                            Clear selection
                        </button>
                    </div>
                    <div class="col-md-6 text-end">
                        <div class="btn-group" role="group">
                            <button type="button" class="btn btn-outline-primary btn-sm" 
                                    data-bulk-action="update">
                                <i class="bi bi-pencil me-1"></i>Bulk Update
                            </button>
                            <button type="button" class="btn btn-outline-warning btn-sm" 
                                    data-bulk-action="adjust-stock">
                                <i class="bi bi-arrows-move me-1"></i>Adjust Stock
                            </button>
                            <button type="button" class="btn btn-outline-success btn-sm" 
                                    data-bulk-action="activate">
                                <i class="bi bi-check-circle me-1"></i>Activate
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm" 
                                    data-bulk-action="deactivate">
                                <i class="bi bi-x-circle me-1"></i>Deactivate
                            </button>
                            <button type="button" class="btn btn-outline-info btn-sm" 
                                    data-bulk-action="export">
                                <i class="bi bi-download me-1"></i>Export
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforebegin', toolbarHtml);
    }

    /**
     * Handle bulk action requests
     */
    async handleBulkAction(action, button) {
        if (this.operationInProgress) {
            this.showAlert('Another operation is already in progress', 'warning');
            return;
        }

        if (this.selectedItems.size === 0) {
            this.showAlert('Please select items first', 'warning');
            return;
        }

        // Disable button during operation
        const originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Processing...';

        try {
            switch(action) {
                case 'update':
                    await this.showBulkUpdateModal();
                    break;
                case 'adjust-stock':
                    await this.showStockAdjustmentModal();
                    break;
                case 'activate':
                    await this.bulkActivateDeactivate(true);
                    break;
                case 'deactivate':
                    await this.bulkActivateDeactivate(false);
                    break;
                case 'export':
                    await this.exportSelected();
                    break;
                default:
                    this.showAlert(`Unknown action: ${action}`, 'error');
            }
        } catch (error) {
            console.error('Bulk action error:', error);
            this.showAlert(`Error performing bulk ${action}: ${error.message}`, 'error');
        } finally {
            // Restore button
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }

    /**
     * Show bulk update modal with form
     */
    async showBulkUpdateModal() {
        const modalHtml = `
            <div class="modal fade" id="bulkUpdateModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="bi bi-pencil-square me-2"></i>
                                Bulk Update ${this.selectedItems.size} Items
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <form id="bulkUpdateForm">
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6 class="text-primary">Pricing Updates</h6>
                                        
                                        <div class="mb-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="updateCostPrice" name="update_fields" value="cost_price">
                                                <label class="form-check-label" for="updateCostPrice">
                                                    Update Cost Price
                                                </label>
                                            </div>
                                            <div class="mt-2">
                                                <select class="form-select form-select-sm" name="cost_price_method">
                                                    <option value="set">Set to specific value</option>
                                                    <option value="increase_percent">Increase by percentage</option>
                                                    <option value="decrease_percent">Decrease by percentage</option>
                                                    <option value="increase_amount">Increase by amount</option>
                                                    <option value="decrease_amount">Decrease by amount</option>
                                                </select>
                                                <input type="number" class="form-control form-control-sm mt-1" 
                                                       name="cost_price_value" placeholder="Value" step="0.01">
                                            </div>
                                        </div>
                                        
                                        <div class="mb-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="updateSellingPrice" name="update_fields" value="selling_price">
                                                <label class="form-check-label" for="updateSellingPrice">
                                                    Update Selling Price
                                                </label>
                                            </div>
                                            <div class="mt-2">
                                                <select class="form-select form-select-sm" name="selling_price_method">
                                                    <option value="set">Set to specific value</option>
                                                    <option value="markup">Apply markup to cost price</option>
                                                    <option value="increase_percent">Increase by percentage</option>
                                                    <option value="decrease_percent">Decrease by percentage</option>
                                                </select>
                                                <input type="number" class="form-control form-control-sm mt-1" 
                                                       name="selling_price_value" placeholder="Value" step="0.01">
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="col-md-6">
                                        <h6 class="text-primary">Product Information</h6>
                                        
                                        <div class="mb-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="updateCategory" name="update_fields" value="category">
                                                <label class="form-check-label" for="updateCategory">
                                                    Update Category
                                                </label>
                                            </div>
                                            <select class="form-select form-select-sm mt-2" name="category_id">
                                                <option value="">Select category...</option>
                                                <!-- Categories will be loaded dynamically -->
                                            </select>
                                        </div>
                                        
                                        <div class="mb-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="updateSupplier" name="update_fields" value="supplier">
                                                <label class="form-check-label" for="updateSupplier">
                                                    Update Supplier
                                                </label>
                                            </div>
                                            <select class="form-select form-select-sm mt-2" name="supplier_id">
                                                <option value="">Select supplier...</option>
                                                <!-- Suppliers will be loaded dynamically -->
                                            </select>
                                        </div>
                                        
                                        <div class="mb-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox" 
                                                       id="updateStatus" name="update_fields" value="is_active">
                                                <label class="form-check-label" for="updateStatus">
                                                    Update Status
                                                </label>
                                            </div>
                                            <select class="form-select form-select-sm mt-2" name="is_active">
                                                <option value="true">Active</option>
                                                <option value="false">Inactive</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row">
                                    <div class="col-12">
                                        <h6 class="text-primary">Stock Management</h6>
                                        
                                        <div class="row">
                                            <div class="col-md-4">
                                                <div class="form-check">
                                                    <input class="form-check-input" type="checkbox" 
                                                           id="updateReorderLevel" name="update_fields" value="reorder_level">
                                                    <label class="form-check-label" for="updateReorderLevel">
                                                        Update Reorder Level
                                                    </label>
                                                </div>
                                                <input type="number" class="form-control form-control-sm mt-1" 
                                                       name="reorder_level" placeholder="Reorder level" min="0">
                                            </div>
                                            
                                            <div class="col-md-4">
                                                <div class="form-check">
                                                    <input class="form-check-input" type="checkbox" 
                                                           id="updateReorderQty" name="update_fields" value="reorder_quantity">
                                                    <label class="form-check-label" for="updateReorderQty">
                                                        Update Reorder Quantity
                                                    </label>
                                                </div>
                                                <input type="number" class="form-control form-control-sm mt-1" 
                                                       name="reorder_quantity" placeholder="Reorder quantity" min="1">
                                            </div>
                                            
                                            <div class="col-md-4">
                                                <div class="form-check">
                                                    <input class="form-check-input" type="checkbox" 
                                                           id="updateMaxStock" name="update_fields" value="max_stock_level">
                                                    <label class="form-check-label" for="updateMaxStock">
                                                        Update Max Stock Level
                                                    </label>
                                                </div>
                                                <input type="number" class="form-control form-control-sm mt-1" 
                                                       name="max_stock_level" placeholder="Max stock level" min="1">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="alert alert-info mt-3">
                                    <i class="bi bi-info-circle me-2"></i>
                                    <strong>Note:</strong> Only checked fields will be updated. 
                                    This operation will affect <strong>${this.selectedItems.size}</strong> products.
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="submit" class="btn btn-primary">
                                    <i class="bi bi-check-circle me-1"></i>Update Products
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if present
        const existingModal = document.getElementById('bulkUpdateModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Load categories and suppliers
        await this.loadSelectOptions();
        
        // Setup form submission
        document.getElementById('bulkUpdateForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.executeBulkUpdate(new FormData(e.target));
        });
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('bulkUpdateModal'));
        modal.show();
    }

    /**
     * Load select options for categories and suppliers
     */
    async loadSelectOptions() {
        try {
            // Load categories
            const categoriesResponse = await fetch('/inventory/api/categories/');
            if (categoriesResponse.ok) {
                const categories = await categoriesResponse.json();
                const categorySelect = document.querySelector('select[name="category_id"]');
                categories.forEach(cat => {
                    categorySelect.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
                });
            }
            
            // Load suppliers
            const suppliersResponse = await fetch('/inventory/api/suppliers/');
            if (suppliersResponse.ok) {
                const suppliers = await suppliersResponse.json();
                const supplierSelect = document.querySelector('select[name="supplier_id"]');
                suppliers.forEach(sup => {
                    supplierSelect.innerHTML += `<option value="${sup.id}">${sup.name}</option>`;
                });
            }
        } catch (error) {
            console.error('Error loading select options:', error);
        }
    }

    /**
     * Execute bulk update operation
     */
    async executeBulkUpdate(formData) {
        const updateData = this.parseUpdateFormData(formData);
        
        // Validate that at least one field is selected for update
        if (updateData.fields.length === 0) {
            this.showAlert('Please select at least one field to update', 'warning');
            return;
        }
        
        // Close update modal and show progress
        bootstrap.Modal.getInstance(document.getElementById('bulkUpdateModal')).hide();
        
        await this.executeOperation('Bulk Update Products', async (progress) => {
            const selectedIds = Array.from(this.selectedItems);
            let completed = 0;
            let errors = [];
            
            // Process in batches of 10 for better performance
            const batchSize = 10;
            for (let i = 0; i < selectedIds.length; i += batchSize) {
                const batch = selectedIds.slice(i, i + batchSize);
                
                try {
                    const response = await fetch('/inventory/api/bulk-update/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCSRFToken()
                        },
                        body: JSON.stringify({
                            product_ids: batch,
                            update_data: updateData
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        completed += batch.length;
                        progress.update(completed, selectedIds.length, 
                            `Updated ${completed} of ${selectedIds.length} products`);
                    } else {
                        errors.push(...(result.errors || ['Unknown error in batch']));
                    }
                    
                } catch (error) {
                    errors.push(`Batch error: ${error.message}`);
                }
            }
            
            return {
                success: errors.length === 0,
                completed,
                total: selectedIds.length,
                errors
            };
        });
        
        // Refresh the page to show updates
        this.refreshProductList();
    }

    /**
     * Parse form data for bulk updates
     */
    parseUpdateFormData(formData) {
        const updateFields = formData.getAll('update_fields');
        const updateData = {
            fields: updateFields,
            values: {}
        };
        
        // Process each selected field
        updateFields.forEach(field => {
            switch(field) {
                case 'cost_price':
                    updateData.values.cost_price = {
                        method: formData.get('cost_price_method'),
                        value: parseFloat(formData.get('cost_price_value'))
                    };
                    break;
                case 'selling_price':
                    updateData.values.selling_price = {
                        method: formData.get('selling_price_method'),
                        value: parseFloat(formData.get('selling_price_value'))
                    };
                    break;
                case 'category':
                    updateData.values.category_id = parseInt(formData.get('category_id'));
                    break;
                case 'supplier':
                    updateData.values.supplier_id = parseInt(formData.get('supplier_id'));
                    break;
                case 'is_active':
                    updateData.values.is_active = formData.get('is_active') === 'true';
                    break;
                case 'reorder_level':
                    updateData.values.reorder_level = parseInt(formData.get('reorder_level'));
                    break;
                case 'reorder_quantity':
                    updateData.values.reorder_quantity = parseInt(formData.get('reorder_quantity'));
                    break;
                case 'max_stock_level':
                    updateData.values.max_stock_level = parseInt(formData.get('max_stock_level'));
                    break;
            }
        });
        
        return updateData;
    }

    /**
     * Show stock adjustment modal
     */
    async showStockAdjustmentModal() {
        const modalHtml = `
            <div class="modal fade" id="bulkStockModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="bi bi-arrows-move me-2"></i>
                                Bulk Stock Adjustment - ${this.selectedItems.size} Items
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <form id="bulkStockForm">
                            <div class="modal-body">
                                <div class="alert alert-warning">
                                    <i class="bi bi-exclamation-triangle me-2"></i>
                                    <strong>Caution:</strong> This will adjust stock levels for all selected products. 
                                    This action creates an audit trail but cannot be undone.
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-6">
                                        <label class="form-label">Adjustment Type</label>
                                        <select class="form-select" name="adjustment_type" required>
                                            <option value="">Choose adjustment type...</option>
                                            <option value="set">Set to specific value</option>
                                            <option value="add">Add to current stock</option>
                                            <option value="subtract">Subtract from current stock</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Quantity</label>
                                        <input type="number" class="form-control" name="quantity" 
                                               placeholder="Enter quantity" min="0" required>
                                    </div>
                                </div>
                                
                                <div class="row mt-3">
                                    <div class="col-md-6">
                                        <label class="form-label">Location (Optional)</label>
                                        <select class="form-select" name="location_id">
                                            <option value="">All locations</option>
                                            <!-- Locations will be loaded dynamically -->
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label class="form-label">Reason</label>
                                        <input type="text" class="form-control" name="reason" 
                                               placeholder="Reason for adjustment" required>
                                    </div>
                                </div>
                                
                                <div class="mt-3">
                                    <label class="form-label">Notes (Optional)</label>
                                    <textarea class="form-control" name="notes" rows="3" 
                                              placeholder="Additional notes about this adjustment"></textarea>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="submit" class="btn btn-warning">
                                    <i class="bi bi-arrows-move me-1"></i>Adjust Stock
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if present
        const existingModal = document.getElementById('bulkStockModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Load locations
        await this.loadLocations();
        
        // Setup form submission
        document.getElementById('bulkStockForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.executeBulkStockAdjustment(new FormData(e.target));
        });
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('bulkStockModal'));
        modal.show();
    }

    /**
     * Load location options
     */
    async loadLocations() {
        try {
            const response = await fetch('/inventory/api/locations/');
            if (response.ok) {
                const locations = await response.json();
                const locationSelect = document.querySelector('select[name="location_id"]');
                locations.forEach(loc => {
                    locationSelect.innerHTML += `<option value="${loc.id}">${loc.name}</option>`;
                });
            }
        } catch (error) {
            console.error('Error loading locations:', error);
        }
    }

    /**
     * Execute bulk stock adjustment
     */
    async executeBulkStockAdjustment(formData) {
        const adjustmentData = {
            adjustment_type: formData.get('adjustment_type'),
            quantity: parseInt(formData.get('quantity')),
            location_id: formData.get('location_id') || null,
            reason: formData.get('reason'),
            notes: formData.get('notes')
        };
        
        // Close modal and show progress
        bootstrap.Modal.getInstance(document.getElementById('bulkStockModal')).hide();
        
        await this.executeOperation('Bulk Stock Adjustment', async (progress) => {
            const selectedIds = Array.from(this.selectedItems);
            let completed = 0;
            let errors = [];
            
            for (let i = 0; i < selectedIds.length; i++) {
                const productId = selectedIds[i];
                
                try {
                    progress.updateCurrent(`Processing product ID: ${productId}`);
                    
                    const response = await fetch('/inventory/api/adjust-stock/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCSRFToken()
                        },
                        body: JSON.stringify({
                            product_id: productId,
                            ...adjustmentData
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        completed++;
                        progress.update(completed, selectedIds.length, 
                            `Adjusted ${completed} of ${selectedIds.length} products`);
                    } else {
                        errors.push(`Product ${productId}: ${result.error}`);
                    }
                    
                } catch (error) {
                    errors.push(`Product ${productId}: ${error.message}`);
                }
                
                // Small delay to prevent overwhelming the server
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            return {
                success: errors.length === 0,
                completed,
                total: selectedIds.length,
                errors
            };
        });
        
        // Refresh the page to show updates
        this.refreshProductList();
    }

    /**
     * Bulk activate or deactivate products
     */
    async bulkActivateDeactivate(activate) {
        const action = activate ? 'activate' : 'deactivate';
        const title = activate ? 'Bulk Activate Products' : 'Bulk Deactivate Products';
        
        // Confirm action
        if (!confirm(`Are you sure you want to ${action} ${this.selectedItems.size} products?`)) {
            return;
        }
        
        await this.executeOperation(title, async (progress) => {
            const selectedIds = Array.from(this.selectedItems);
            let completed = 0;
            let errors = [];
            
            // Process in batches
            const batchSize = 20;
            for (let i = 0; i < selectedIds.length; i += batchSize) {
                const batch = selectedIds.slice(i, i + batchSize);
                
                try {
                    const response = await fetch('/inventory/api/bulk-activate/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCSRFToken()
                        },
                        body: JSON.stringify({
                            product_ids: batch,
                            is_active: activate
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        completed += batch.length;
                        progress.update(completed, selectedIds.length, 
                            `${activate ? 'Activated' : 'Deactivated'} ${completed} of ${selectedIds.length} products`);
                    } else {
                        errors.push(...(result.errors || ['Unknown error in batch']));
                    }
                    
                } catch (error) {
                    errors.push(`Batch error: ${error.message}`);
                }
            }
            
            return {
                success: errors.length === 0,
                completed,
                total: selectedIds.length,
                errors
            };
        });
        
        this.refreshProductList();
    }

    /**
     * Export selected products
     */
    async exportSelected() {
        try {
            const selectedIds = Array.from(this.selectedItems);
            
            // Create export form
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/inventory/products/export/';
            
            // Add CSRF token
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = this.getCSRFToken();
            form.appendChild(csrfInput);
            
            // Add selected product IDs
            selectedIds.forEach(id => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'product_ids';
                input.value = id;
                form.appendChild(input);
            });
            
            // Add to page and submit
            document.body.appendChild(form);
            form.submit();
            document.body.removeChild(form);
            
            this.showAlert(`Export started for ${selectedIds.length} products`, 'success');
            
        } catch (error) {
            console.error('Export error:', error);
            this.showAlert(`Export failed: ${error.message}`, 'error');
        }
    }

    /**
     * Generic operation executor with progress tracking
     */
    async executeOperation(title, operationFunc) {
        this.operationInProgress = true;
        this.currentOperation = title;
        
        // Setup progress modal
        document.getElementById('progressTitle').textContent = title;
        document.getElementById('itemsCount').textContent = this.selectedItems.size;
        document.getElementById('successCount').textContent = '0';
        document.getElementById('errorCount').textContent = '0';
        document.getElementById('progressCount').textContent = `0 / ${this.selectedItems.size}`;
        document.getElementById('overallProgress').style.width = '0%';
        document.getElementById('progressText').textContent = 'Starting operation...';
        document.getElementById('currentItem').textContent = 'Preparing...';
        document.getElementById('errorLogContainer').style.display = 'none';
        document.getElementById('errorLog').innerHTML = '';
        document.getElementById('cancelOperation').style.display = 'inline-block';
        document.getElementById('closeProgress').style.display = 'none';
        
        this.progressModal.show();
        
        // Progress update functions
        const progress = {
            update: (completed, total, message) => {
                const percentage = Math.round((completed / total) * 100);
                document.getElementById('overallProgress').style.width = `${percentage}%`;
                document.getElementById('progressText').textContent = message;
                document.getElementById('progressCount').textContent = `${completed} / ${total}`;
                document.getElementById('successCount').textContent = completed;
            },
            updateCurrent: (currentItem) => {
                document.getElementById('currentItem').textContent = currentItem;
            },
            addError: (error) => {
                const errorLog = document.getElementById('errorLog');
                errorLog.innerHTML += `<li>${error}</li>`;
                document.getElementById('errorLogContainer').style.display = 'block';
                
                const errorCount = document.getElementById('errorCount');
                errorCount.textContent = parseInt(errorCount.textContent) + 1;
            }
        };
        
        try {
            const result = await operationFunc(progress);
            
            // Update final progress
            if (result.errors && result.errors.length > 0) {
                result.errors.forEach(error => progress.addError(error));
            }
            
            const successMessage = result.success ? 
                `Operation completed successfully! Processed ${result.completed} items.` :
                `Operation completed with ${result.errors.length} errors. ${result.completed} items processed successfully.`;
            
            document.getElementById('progressText').textContent = successMessage;
            
            this.showAlert(successMessage, result.success ? 'success' : 'warning');
            
        } catch (error) {
            console.error('Operation error:', error);
            document.getElementById('progressText').textContent = `Operation failed: ${error.message}`;
            progress.addError(`Fatal error: ${error.message}`);
            this.showAlert(`Operation failed: ${error.message}`, 'error');
        } finally {
            this.operationInProgress = false;
            document.getElementById('cancelOperation').style.display = 'none';
            document.getElementById('closeProgress').style.display = 'inline-block';
        }
    }

    /**
     * Cancel current operation
     */
    cancelCurrentOperation() {
        if (this.operationInProgress) {
            this.operationInProgress = false;
            document.getElementById('progressText').textContent = 'Operation cancelled by user';
            document.getElementById('cancelOperation').style.display = 'none';
            document.getElementById('closeProgress').style.display = 'inline-block';
            this.showAlert('Operation cancelled', 'warning');
        }
    }

    /**
     * Reset progress modal
     */
    resetProgress() {
        this.operationInProgress = false;
        this.currentOperation = null;
    }

    /**
     * Toggle select all functionality
     */
    toggleSelectAll(checked) {
        const checkboxes = document.querySelectorAll('.item-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            this.handleItemSelection(checkbox);
        });
    }

    /**
     * Select all visible items
     */
    selectAllVisible() {
        const selectAllCheckbox = document.getElementById('selectAll');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = true;
            this.toggleSelectAll(true);
        }
    }

    /**
     * Handle individual item selection
     */
    handleItemSelection(checkbox) {
        const itemId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedItems.add(itemId);
        } else {
            this.selectedItems.delete(itemId);
        }
        
        this.updateSelectionToolbar();
        this.updateSelectAllState();
    }

    /**
     * Update select all checkbox state
     */
    updateSelectAllState() {
        const selectAllCheckbox = document.getElementById('selectAll');
        const itemCheckboxes = document.querySelectorAll('.item-checkbox');
        
        if (selectAllCheckbox && itemCheckboxes.length > 0) {
            const checkedCount = document.querySelectorAll('.item-checkbox:checked').length;
            
            if (checkedCount === 0) {
                selectAllCheckbox.indeterminate = false;
                selectAllCheckbox.checked = false;
            } else if (checkedCount === itemCheckboxes.length) {
                selectAllCheckbox.indeterminate = false;
                selectAllCheckbox.checked = true;
            } else {
                selectAllCheckbox.indeterminate = true;
                selectAllCheckbox.checked = false;
            }
        }
    }

    /**
     * Update selection toolbar visibility and count
     */
    updateSelectionToolbar() {
        const toolbar = document.querySelector('.bulk-actions-toolbar');
        const countElement = document.getElementById('selectedCount');
        
        if (toolbar) {
            if (this.selectedItems.size > 0) {
                toolbar.style.display = 'block';
                if (countElement) {
                    countElement.textContent = this.selectedItems.size;
                }
            } else {
                toolbar.style.display = 'none';
            }
        }
    }

    /**
     * Clear all selections
     */
    clearSelection() {
        this.selectedItems.clear();
        document.querySelectorAll('.item-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSelectionToolbar();
        this.updateSelectAllState();
    }

    /**
     * Refresh product list after operations
     */
    refreshProductList() {
        // Clear selections
        this.clearSelection();
        
        // Reload page or update content via AJAX
        if (typeof window.InventoryApp?.updateProductList === 'function') {
            window.InventoryApp.updateProductList();
        } else {
            // Fallback to page reload
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    }

    /**
     * Get CSRF token for API requests
     */
    getCSRFToken() {
        const csrfCookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        
        if (csrfCookie) {
            return csrfCookie.split('=')[1];
        }
        
        // Fallback to meta tag
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        return csrfMeta ? csrfMeta.getAttribute('content') : '';
    }

    /**
     * Show alert notification
     */
    showAlert(message, type = 'info') {
        const alertTypes = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info'
        };
        
        const alertHtml = `
            <div class="alert alert-${alertTypes[type]} alert-dismissible fade show position-fixed" 
                 style="top: 80px; right: 20px; z-index: 1060; min-width: 350px;">
                <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', alertHtml);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            const alerts = document.querySelectorAll('.alert.position-fixed');
            alerts.forEach(alert => {
                if (alert.parentNode) {
                    alert.remove();
                }
            });
        }, 5000);
    }
}

// Initialize bulk operations manager
const bulkOps = new BulkOperationsManager();

// Export for global access
window.BulkOperationsManager = BulkOperationsManager;
window.bulkOps = bulkOps;
