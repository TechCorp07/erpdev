/**
 * Quote Builder JavaScript
 * 
 * This script powers the interactive quote building experience. It handles:
 * - Real-time product search and selection
 * - Dynamic item addition/removal
 * - Live price calculations
 * - Form validation and user feedback
 * 
 * The code is structured as a JavaScript class to maintain clean organization
 * and make the functionality easy to extend and maintain.
 */

class QuoteBuilder {
    constructor(quoteId) {
        this.quoteId = quoteId;
        this.debounceTimeout = null;
        this.isLoading = false;
        
        // Initialize the quote builder when DOM is ready
        this.init();
    }
    
    init() {
        console.log('Initializing Quote Builder for quote:', this.quoteId);
        
        // Bind event handlers
        this.bindEvents();
        
        // Initialize any existing quote items
        this.initializeExistingItems();
        
        // Set up auto-save functionality
        this.setupAutoSave();
        
        // Initialize product search
        this.initializeProductSearch();
    }
    
    bindEvents() {
        /**
         * Set up all event listeners for the quote builder interface.
         * This method connects user interactions to the appropriate handlers.
         */
        
        // Product search functionality
        const productSearchInput = document.getElementById('product-search');
        if (productSearchInput) {
            productSearchInput.addEventListener('input', (e) => {
                this.handleProductSearch(e.target.value);
            });
            
            productSearchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.handleProductSearchEnter();
                }
            });
        }
        
        // Add item button
        const addItemBtn = document.getElementById('add-item-btn');
        if (addItemBtn) {
            addItemBtn.addEventListener('click', () => {
                this.showAddItemModal();
            });
        }
        
        // Quick add buttons for common items
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-add-product')) {
                const productId = e.target.dataset.productId;
                this.quickAddProduct(productId);
            }
        });
        
        // Item quantity and price change handlers
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('item-quantity')) {
                this.handleQuantityChange(e.target);
            } else if (e.target.classList.contains('item-price')) {
                this.handlePriceChange(e.target);
            }
        });
        
        // Remove item buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-item-btn')) {
                const itemId = e.target.dataset.itemId;
                this.removeItem(itemId);
            }
        });
        
        // Quote-level changes (discount, tax rate)
        const discountInput = document.getElementById('quote-discount');
        if (discountInput) {
            discountInput.addEventListener('change', () => {
                this.updateQuoteDiscount();
            });
        }
        
        const taxRateInput = document.getElementById('quote-tax-rate');
        if (taxRateInput) {
            taxRateInput.addEventListener('change', () => {
                this.updateQuoteTaxRate();
            });
        }
    }
    
    handleProductSearch(query) {
        /**
         * Handle real-time product search with debouncing to avoid excessive API calls.
         * This provides instant feedback while being efficient with server resources.
         */
        
        // Clear previous timeout
        if (this.debounceTimeout) {
            clearTimeout(this.debounceTimeout);
        }
        
        // Don't search for very short queries
        if (query.length < 2) {
            this.clearSearchResults();
            return;
        }
        
        // Debounce the search to avoid too many requests
        this.debounceTimeout = setTimeout(() => {
            this.performProductSearch(query);
        }, 300); // 300ms delay
    }
    
    async performProductSearch(query) {
        /**
         * Perform the actual product search and display results.
         * This creates a smooth, responsive search experience.
         */
        
        try {
            this.showSearchLoading();
            
            const response = await fetch(`/quotes/ajax/search-products/?q=${encodeURIComponent(query)}`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });
            
            const data = await response.json();
            
            if (data.products) {
                this.displaySearchResults(data.products);
            } else {
                this.showSearchError('No products found');
            }
            
        } catch (error) {
            console.error('Product search error:', error);
            this.showSearchError('Search failed. Please try again.');
        } finally {
            this.hideSearchLoading();
        }
    }
    
    displaySearchResults(products) {
        /**
         * Display product search results in an attractive, user-friendly format.
         * Each result shows key information and provides easy adding functionality.
         */
        
        const resultsContainer = document.getElementById('search-results');
        if (!resultsContainer) return;
        
        if (products.length === 0) {
            resultsContainer.innerHTML = `
                <div class="text-center py-3 text-muted">
                    <i class="bi bi-search fs-3 mb-2"></i>
                    <p>No products found matching your search.</p>
                </div>
            `;
            return;
        }
        
        const resultsHTML = products.map(product => `
            <div class="search-result-item border rounded p-3 mb-2" data-product-id="${product.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${this.escapeHtml(product.name)}</h6>
                        <p class="text-muted small mb-1">${this.escapeHtml(product.description)}</p>
                        <div class="d-flex align-items-center gap-3">
                            <span class="badge bg-secondary">${product.sku}</span>
                            ${product.category ? `<span class="text-muted small">${product.category}</span>` : ''}
                            ${product.current_stock > 0 ? 
                                `<span class="text-success small"><i class="bi bi-check-circle"></i> In Stock (${product.current_stock})</span>` :
                                `<span class="text-warning small"><i class="bi bi-clock"></i> Order Required</span>`
                            }
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="fw-bold text-primary">$${product.suggested_price.toFixed(2)}</div>
                        <button class="btn btn-sm btn-outline-primary mt-1 quick-add-product" 
                                data-product-id="${product.id}">
                            <i class="bi bi-plus"></i> Add
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        
        resultsContainer.innerHTML = resultsHTML;
        
        // Add click handlers for detailed product view
        resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('quick-add-product')) {
                    const productId = item.dataset.productId;
                    this.showProductDetails(productId);
                }
            });
        });
    }
    
    async quickAddProduct(productId) {
        /**
         * Quickly add a product to the quote with default settings.
         * This is perfect for fast quote building when you know exactly what you want.
         */
        
        try {
            this.setLoading(true);
            
            // Get product details first
            const productResponse = await fetch(`/quotes/ajax/product-details/${productId}/`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            
            const productData = await productResponse.json();
            
            if (!productData.success) {
                throw new Error(productData.error || 'Failed to get product details');
            }
            
            const product = productData.product;
            
            // Add the product with intelligent defaults
            const itemData = {
                product_id: product.id,
                description: product.name,
                quantity: product.minimum_quantity || 1,
                unit_price: product.pricing_options.find(opt => opt.level === 'standard')?.price || product.suggested_price,
                source_type: product.availability.in_stock ? 'stock' : 'order',
            };
            
            await this.addItemToQuote(itemData);
            
            this.showSuccess(`Added ${product.name} to quote`);
            
        } catch (error) {
            console.error('Quick add error:', error);
            this.showError('Failed to add product. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    async addItemToQuote(itemData) {
        /**
         * Add an item to the quote using the AJAX endpoint.
         * This method handles the server communication and UI updates.
         */
        
        try {
            const response = await fetch(`/quotes/${this.quoteId}/add-item/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify(itemData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Add the new item to the UI
                this.addItemToUI(data.item);
                
                // Update quote totals
                this.updateQuoteTotals(data.quote_totals);
                
                // Clear the search
                this.clearProductSearch();
                
                return data.item;
            } else {
                throw new Error(data.error || 'Failed to add item');
            }
            
        } catch (error) {
            console.error('Add item error:', error);
            throw error;
        }
    }
    
    addItemToUI(item) {
        /**
         * Add a new item row to the quote builder interface.
         * This creates a clean, editable representation of the quote item.
         */
        
        const itemsContainer = document.getElementById('quote-items');
        if (!itemsContainer) return;
        
        const itemRow = document.createElement('div');
        itemRow.className = 'quote-item-row border rounded p-3 mb-3';
        itemRow.dataset.itemId = item.id;
        
        itemRow.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-4">
                    <input type="text" class="form-control item-description" 
                           value="${this.escapeHtml(item.description)}"
                           data-item-id="${item.id}">
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control item-quantity" 
                           value="${item.quantity}" min="1" step="1"
                           data-item-id="${item.id}">
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control item-price" 
                           value="${item.unit_price}" min="0" step="0.01"
                           data-item-id="${item.id}">
                </div>
                <div class="col-md-2">
                    <div class="fw-bold item-total">$${item.total_price.toFixed(2)}</div>
                    <small class="text-muted">${item.source_type}</small>
                </div>
                <div class="col-md-2 text-end">
                    <button class="btn btn-sm btn-outline-danger remove-item-btn" 
                            data-item-id="${item.id}" title="Remove item">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `;
        
        itemsContainer.appendChild(itemRow);
        
        // Add change handlers for the new inputs
        this.bindItemEvents(itemRow);
    }
    
    bindItemEvents(itemRow) {
        /**
         * Bind event handlers to a specific item row.
         * This ensures new items have proper interactive functionality.
         */
        
        const quantityInput = itemRow.querySelector('.item-quantity');
        const priceInput = itemRow.querySelector('.item-price');
        const descriptionInput = itemRow.querySelector('.item-description');
        
        if (quantityInput) {
            quantityInput.addEventListener('change', () => this.handleQuantityChange(quantityInput));
            quantityInput.addEventListener('blur', () => this.handleQuantityChange(quantityInput));
        }
        
        if (priceInput) {
            priceInput.addEventListener('change', () => this.handlePriceChange(priceInput));
            priceInput.addEventListener('blur', () => this.handlePriceChange(priceInput));
        }
        
        if (descriptionInput) {
            descriptionInput.addEventListener('change', () => this.handleDescriptionChange(descriptionInput));
            descriptionInput.addEventListener('blur', () => this.handleDescriptionChange(descriptionInput));
        }
    }
    
    async handleQuantityChange(input) {
        /**
         * Handle quantity changes with real-time updates and validation.
         */
        
        const itemId = input.dataset.itemId;
        const newQuantity = parseInt(input.value);
        
        if (newQuantity < 1) {
            input.value = 1;
            return;
        }
        
        await this.updateQuoteItem(itemId, { quantity: newQuantity });
    }
    
    async handlePriceChange(input) {
        /**
         * Handle price changes with validation and profit margin warnings.
         */
        
        const itemId = input.dataset.itemId;
        const newPrice = parseFloat(input.value);
        
        if (newPrice < 0) {
            input.value = 0;
            return;
        }
        
        await this.updateQuoteItem(itemId, { unit_price: newPrice });
    }
    
    async handleDescriptionChange(input) {
        /**
         * Handle description changes with auto-save functionality.
         */
        
        const itemId = input.dataset.itemId;
        const newDescription = input.value.trim();
        
        if (newDescription.length === 0) {
            this.showError('Description cannot be empty');
            return;
        }
        
        await this.updateQuoteItem(itemId, { description: newDescription });
    }
    
    async updateQuoteItem(itemId, updates) {
        /**
         * Update a quote item using the AJAX endpoint and refresh the UI.
         */
        
        try {
            const response = await fetch(`/quotes/${this.quoteId}/items/${itemId}/update/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify(updates)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update the UI with new values
                this.updateItemInUI(itemId, data.item);
                
                // Update quote totals
                this.updateQuoteTotals(data.quote_totals);
                
                // Show any warnings
                if (data.warning) {
                    this.showWarning(data.warning);
                }
                
            } else {
                throw new Error(data.error || 'Failed to update item');
            }
            
        } catch (error) {
            console.error('Update item error:', error);
            this.showError('Failed to update item. Please try again.');
        }
    }
    
    updateItemInUI(itemId, itemData) {
        /**
         * Update the UI representation of a quote item with new data.
         */
        
        const itemRow = document.querySelector(`[data-item-id="${itemId}"]`);
        if (!itemRow) return;
        
        // Update the total price display
        const totalDisplay = itemRow.querySelector('.item-total');
        if (totalDisplay) {
            totalDisplay.textContent = `$${itemData.total_price.toFixed(2)}`;
        }
        
        // Update input values if they're different (avoids cursor jumping)
        const quantityInput = itemRow.querySelector('.item-quantity');
        if (quantityInput && parseInt(quantityInput.value) !== itemData.quantity) {
            quantityInput.value = itemData.quantity;
        }
        
        const priceInput = itemRow.querySelector('.item-price');
        if (priceInput && parseFloat(priceInput.value) !== itemData.unit_price) {
            priceInput.value = itemData.unit_price;
        }
        
        const descriptionInput = itemRow.querySelector('.item-description');
        if (descriptionInput && descriptionInput.value !== itemData.description) {
            descriptionInput.value = itemData.description;
        }
    }
    
    updateQuoteTotals(totals) {
        /**
         * Update the quote totals display throughout the interface.
         */
        
        const elements = {
            'quote-subtotal': totals.subtotal,
            'quote-tax-amount': totals.tax_amount,
            'quote-total-amount': totals.total_amount,
        };
        
        Object.entries(elements).forEach(([elementId, value]) => {
            const element = document.getElementById(elementId);
            if (element) {
                element.textContent = `$${value.toFixed(2)}`;
            }
        });
        
        // Update item count
        const itemCountElement = document.getElementById('quote-item-count');
        if (itemCountElement && totals.item_count !== undefined) {
            itemCountElement.textContent = totals.item_count;
        }
    }
    
    // Utility methods for user feedback and interaction
    
    showSuccess(message) {
        this.showToast(message, 'success');
    }
    
    showError(message) {
        this.showToast(message, 'danger');
    }
    
    showWarning(message) {
        this.showToast(message, 'warning');
    }
    
    showToast(message, type = 'info') {
        /**
         * Display user feedback using Bootstrap toast notifications.
         */
        
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.id = toastId;
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${this.escapeHtml(message)}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
    
    createToastContainer() {
        /**
         * Create a toast container if it doesn't exist.
         */
        
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
        return container;
    }
    
    getCsrfToken() {
        /**
         * Get the CSRF token for AJAX requests.
         */
        
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
    
    escapeHtml(text) {
        /**
         * Escape HTML to prevent XSS attacks.
         */
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    setLoading(isLoading) {
        /**
         * Show/hide loading indicators throughout the interface.
         */
        
        this.isLoading = isLoading;
        
        const loadingElements = document.querySelectorAll('.loading-indicator');
        loadingElements.forEach(element => {
            element.style.display = isLoading ? 'block' : 'none';
        });
        
        const actionButtons = document.querySelectorAll('.quote-action-btn');
        actionButtons.forEach(button => {
            button.disabled = isLoading;
        });
    }
    
    clearProductSearch() {
        /**
         * Clear the product search input and results.
         */
        
        const searchInput = document.getElementById('product-search');
        if (searchInput) {
            searchInput.value = '';
        }
        
        this.clearSearchResults();
    }
    
    clearSearchResults() {
        const resultsContainer = document.getElementById('search-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
        }
    }
}

// Initialize the quote builder when the page loads
document.addEventListener('DOMContentLoaded', function() {
    const quoteIdElement = document.getElementById('quote-id');
    if (quoteIdElement) {
        const quoteId = quoteIdElement.value;
        window.quoteBuilder = new QuoteBuilder(quoteId);
    }
});