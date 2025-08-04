/**
 * Barcode Scanner - Barcode & QR Code Integration
 * 
 * This file handles barcode scanning functionality including:
 * - Camera-based barcode scanning
 * - QR code generation and scanning
 * - Barcode validation and lookup
 * - Quick product search via barcode
 * - Mobile barcode scanning optimization
 */

(function($) {
    'use strict';

    // =====================================
    // BARCODE SCANNER MODULE
    // =====================================

    const BarcodeScanner = {
        // Configuration
        config: {
            endpoints: {
                lookup: '/inventory/api/barcode/lookup/',
                scan: '/inventory/api/barcode/scan/',
                generate: '/inventory/api/qr/generate/',
                validate: '/inventory/api/barcode/validate/'
            },
            scanner: {
                width: 640,
                height: 480,
                facingMode: 'environment', // Use back camera
                formats: [
                    'code_128',
                    'code_39',
                    'ean_13',
                    'ean_8',
                    'upc_a',
                    'upc_e',
                    'qr_code',
                    'data_matrix'
                ]
            },
            audio: {
                enabled: true,
                successSound: '/static/inventory/sounds/beep-success.mp3',
                errorSound: '/static/inventory/sounds/beep-error.mp3'
            }
        },

        // Scanner state
        isScanning: false,
        scannerStream: null,
        scannerElement: null,
        lastScanTime: 0,
        scanCooldown: 1000, // 1 second between scans

        // Audio elements
        audioElements: {},

        /**
         * Initialize Barcode Scanner
         */
        init: function() {
            this.checkSupport();
            this.bindEvents();
            this.createScannerModal();
            this.initializeAudio();
            this.setupKeyboardShortcuts();
        },

        /**
         * Check browser support for camera access
         */
        checkSupport: function() {
            this.isSupported = !!(
                navigator.mediaDevices &&
                navigator.mediaDevices.getUserMedia &&
                window.BarcodeDetector
            );

            if (!this.isSupported) {
                console.warn('Barcode scanning not supported in this browser');
                // Hide scanner buttons if not supported
                $('.barcode-scan-btn').hide();
            }
        },

        /**
         * Bind event handlers
         */
        bindEvents: function() {
            // Scanner trigger buttons
            $(document).on('click', '.barcode-scan-btn', this.openScanner.bind(this));
            $(document).on('click', '.qr-generate-btn', this.generateQRCode.bind(this));
            
            // Manual barcode input
            $(document).on('input', '.barcode-input', this.handleBarcodeInput.bind(this));
            $(document).on('keypress', '.barcode-input', this.handleBarcodeKeypress.bind(this));
            
            // Scanner modal events
            $(document).on('click', '#startScanBtn', this.startScanning.bind(this));
            $(document).on('click', '#stopScanBtn', this.stopScanning.bind(this));
            $(document).on('hidden.bs.modal', '#barcodeScannerModal', this.cleanupScanner.bind(this));
            
            // Camera selection
            $(document).on('change', '#cameraSelect', this.switchCamera.bind(this));
            
            // Barcode lookup results
            $(document).on('click', '.barcode-result-item', this.selectBarcodeResult.bind(this));
        },

        /**
         * Create scanner modal
         */
        createScannerModal: function() {
            if ($('#barcodeScannerModal').length) return;

            const modalHtml = `
                <div class="modal fade" id="barcodeScannerModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-upc-scan me-2"></i>Barcode Scanner
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-lg-8">
                                        <div class="scanner-container position-relative">
                                            <video id="scannerVideo" class="w-100" style="max-height: 400px; border-radius: 0.5rem;"></video>
                                            <canvas id="scannerCanvas" class="d-none"></canvas>
                                            
                                            <!-- Scanner overlay -->
                                            <div class="scanner-overlay position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center">
                                                <div class="scanner-frame border border-3 border-primary" style="width: 300px; height: 150px; border-style: dashed !important;"></div>
                                            </div>
                                            
                                            <!-- Scanner status -->
                                            <div class="scanner-status position-absolute bottom-0 start-0 w-100 p-3">
                                                <div class="bg-dark bg-opacity-75 text-white p-2 rounded text-center">
                                                    <span id="scannerStatusText">Ready to scan</span>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <!-- Scanner controls -->
                                        <div class="scanner-controls mt-3 d-flex gap-2 justify-content-center">
                                            <button type="button" class="btn btn-success" id="startScanBtn">
                                                <i class="bi bi-play-fill me-1"></i>Start Scan
                                            </button>
                                            <button type="button" class="btn btn-danger d-none" id="stopScanBtn">
                                                <i class="bi bi-stop-fill me-1"></i>Stop Scan
                                            </button>
                                            <select class="form-select" id="cameraSelect" style="max-width: 200px;">
                                                <option value="">Select Camera</option>
                                            </select>
                                        </div>
                                    </div>
                                    
                                    <div class="col-lg-4">
                                        <h6>Manual Entry</h6>
                                        <div class="input-group mb-3">
                                            <input type="text" class="form-control" id="manualBarcodeInput" 
                                                   placeholder="Enter barcode manually">
                                            <button class="btn btn-outline-primary" type="button" id="lookupBarcodeBtn">
                                                <i class="bi bi-search"></i>
                                            </button>
                                        </div>
                                        
                                        <h6>Scan History</h6>
                                        <div id="scanHistory" class="scan-history" style="max-height: 250px; overflow-y: auto;">
                                            <!-- Scan history will appear here -->
                                        </div>
                                        
                                        <h6 class="mt-3">Tips</h6>
                                        <ul class="small text-muted">
                                            <li>Hold device steady</li>
                                            <li>Ensure good lighting</li>
                                            <li>Keep barcode within frame</li>
                                            <li>Clean camera lens if blurry</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            $('body').append(modalHtml);
            
            // Bind additional events
            $('#lookupBarcodeBtn').on('click', this.manualBarcodeLookup.bind(this));
            $('#manualBarcodeInput').on('keypress', (e) => {
                if (e.which === 13) { // Enter key
                    this.manualBarcodeLookup();
                }
            });
        },

        /**
         * Initialize audio elements
         */
        initializeAudio: function() {
            if (!this.config.audio.enabled) return;

            // Create audio elements
            this.audioElements.success = new Audio();
            this.audioElements.error = new Audio();
            
            // Set sources (fallback to beep sounds if files don't exist)
            this.audioElements.success.src = this.config.audio.successSound;
            this.audioElements.error.src = this.config.audio.errorSound;
            
            // Handle load errors gracefully
            Object.values(this.audioElements).forEach(audio => {
                audio.addEventListener('error', () => {
                    console.warn('Could not load audio file');
                });
            });
        },

        /**
         * Setup keyboard shortcuts
         */
        setupKeyboardShortcuts: function() {
            $(document).on('keydown', (e) => {
                // Ctrl/Cmd + B to open barcode scanner
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
                    e.preventDefault();
                    if (this.isSupported) {
                        this.openScanner();
                    }
                }
            });
        },

        /**
         * Open barcode scanner modal
         */
        openScanner: function(event) {
            if (event) {
                event.preventDefault();
            }

            if (!this.isSupported) {
                window.InventoryApp.Notifications.error('Barcode scanning not supported in this browser');
                return;
            }

            const $modal = $('#barcodeScannerModal');
            $modal.modal('show');
            
            // Load available cameras
            this.loadCameras();
        },

        /**
         * Load available cameras
         */
        loadCameras: function() {
            navigator.mediaDevices.enumerateDevices()
                .then(devices => {
                    const videoDevices = devices.filter(device => device.kind === 'videoinput');
                    const $select = $('#cameraSelect');
                    
                    $select.empty().append('<option value="">Select Camera</option>');
                    
                    videoDevices.forEach((device, index) => {
                        const label = device.label || `Camera ${index + 1}`;
                        $select.append(`<option value="${device.deviceId}">${label}</option>`);
                    });
                    
                    // Auto-select back camera if available
                    const backCamera = videoDevices.find(device => 
                        device.label.toLowerCase().includes('back') ||
                        device.label.toLowerCase().includes('rear') ||
                        device.label.toLowerCase().includes('environment')
                    );
                    
                    if (backCamera) {
                        $select.val(backCamera.deviceId);
                    }
                })
                .catch(err => {
                    console.error('Error enumerating devices:', err);
                });
        },

        /**
         * Start scanning process
         */
        startScanning: function() {
            if (this.isScanning) return;

            const deviceId = $('#cameraSelect').val();
            if (!deviceId) {
                window.InventoryApp.Notifications.warning('Please select a camera first');
                return;
            }

            this.updateScannerStatus('Starting camera...', 'info');
            
            const constraints = {
                video: {
                    deviceId: { exact: deviceId },
                    width: { ideal: this.config.scanner.width },
                    height: { ideal: this.config.scanner.height }
                }
            };

            navigator.mediaDevices.getUserMedia(constraints)
                .then(stream => {
                    this.scannerStream = stream;
                    this.scannerElement = document.getElementById('scannerVideo');
                    this.scannerElement.srcObject = stream;
                    this.scannerElement.play();
                    
                    this.isScanning = true;
                    this.updateScannerUI(true);
                    this.updateScannerStatus('Camera ready - position barcode in frame', 'success');
                    
                    // Start barcode detection
                    this.startBarcodeDetection();
                })
                .catch(err => {
                    console.error('Error accessing camera:', err);
                    this.updateScannerStatus('Error: Could not access camera', 'error');
                    window.InventoryApp.Notifications.error('Could not access camera. Please check permissions.');
                });
        },

        /**
         * Stop scanning process
         */
        stopScanning: function() {
            if (!this.isScanning) return;

            if (this.scannerStream) {
                this.scannerStream.getTracks().forEach(track => track.stop());
                this.scannerStream = null;
            }
            
            if (this.scannerElement) {
                this.scannerElement.srcObject = null;
            }
            
            if (this.detectionInterval) {
                clearInterval(this.detectionInterval);
                this.detectionInterval = null;
            }
            
            this.isScanning = false;
            this.updateScannerUI(false);
            this.updateScannerStatus('Scanner stopped', 'info');
        },

        /**
         * Start barcode detection loop
         */
        startBarcodeDetection: function() {
            if (!window.BarcodeDetector) {
                this.updateScannerStatus('BarcodeDetector API not supported', 'error');
                return;
            }

            const detector = new BarcodeDetector({
                formats: this.config.scanner.formats
            });

            const canvas = document.getElementById('scannerCanvas');
            const context = canvas.getContext('2d');

            this.detectionInterval = setInterval(() => {
                if (!this.isScanning || !this.scannerElement.videoWidth) return;

                // Set canvas size to match video
                canvas.width = this.scannerElement.videoWidth;
                canvas.height = this.scannerElement.videoHeight;

                // Draw current video frame to canvas
                context.drawImage(this.scannerElement, 0, 0, canvas.width, canvas.height);

                // Detect barcodes
                detector.detect(canvas)
                    .then(barcodes => {
                        if (barcodes.length > 0) {
                            this.handleBarcodeDetected(barcodes[0]);
                        }
                    })
                    .catch(err => {
                        console.error('Barcode detection error:', err);
                    });
            }, 100); // Check every 100ms
        },

        /**
         * Handle detected barcode
         */
        handleBarcodeDetected: function(barcode) {
            const now = Date.now();
            
            // Prevent duplicate scans within cooldown period
            if (now - this.lastScanTime < this.scanCooldown) {
                return;
            }
            
            this.lastScanTime = now;
            
            const barcodeValue = barcode.rawValue;
            this.updateScannerStatus(`Scanned: ${barcodeValue}`, 'success');
            
            // Play success sound
            this.playSound('success');
            
            // Add to scan history
            this.addToScanHistory(barcodeValue, barcode.format);
            
            // Lookup product by barcode
            this.lookupProductByBarcode(barcodeValue);
            
            // Trigger barcode scanned event
            $(document).trigger('barcode:scanned', {
                value: barcodeValue,
                format: barcode.format,
                timestamp: now
            });
        },

        /**
         * Lookup product by barcode
         */
        lookupProductByBarcode: function(barcode) {
            window.InventoryApp.Ajax.get(this.config.endpoints.lookup + barcode + '/')
                .done(response => {
                    if (response.success && response.product) {
                        this.handleProductFound(response.product);
                    } else {
                        this.handleProductNotFound(barcode);
                    }
                })
                .fail(() => {
                    this.updateScannerStatus('Error looking up product', 'error');
                    this.playSound('error');
                });
        },

        /**
         * Handle product found
         */
        handleProductFound: function(product) {
            const resultHtml = `
                <div class="alert alert-success">
                    <h6><i class="bi bi-check-circle me-2"></i>Product Found</h6>
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${product.name}</strong><br>
                            <small>SKU: ${product.sku} | Stock: ${product.current_stock}</small>
                        </div>
                        <div>
                            <a href="/inventory/products/${product.id}/" class="btn btn-sm btn-primary" target="_blank">
                                View Details
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            $('#scanHistory').prepend(resultHtml);
            
            // Trigger product found event
            $(document).trigger('barcode:product:found', { product: product });
            
            window.InventoryApp.Notifications.success(`Found: ${product.name}`);
        },

        /**
         * Handle product not found
         */
        handleProductNotFound: function(barcode) {
            const resultHtml = `
                <div class="alert alert-warning">
                    <h6><i class="bi bi-exclamation-triangle me-2"></i>Product Not Found</h6>
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <small>Barcode: ${barcode}</small>
                        </div>
                        <div>
                            <a href="/inventory/products/create/?barcode=${barcode}" class="btn btn-sm btn-outline-primary" target="_blank">
                                Add Product
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            $('#scanHistory').prepend(resultHtml);
            
            this.playSound('error');
            window.InventoryApp.Notifications.warning('Product not found in inventory');
            
            // Trigger product not found event
            $(document).trigger('barcode:product:not_found', { barcode: barcode });
        },

        /**
         * Manual barcode lookup
         */
        manualBarcodeLookup: function() {
            const barcode = $('#manualBarcodeInput').val().trim();
            
            if (!barcode) {
                window.InventoryApp.Notifications.warning('Please enter a barcode');
                return;
            }
            
            this.lookupProductByBarcode(barcode);
            $('#manualBarcodeInput').val('');
        },

        /**
         * Add to scan history
         */
        addToScanHistory: function(barcode, format) {
            const timestamp = window.InventoryApp.Utils.formatDate(new Date(), 'time');
            
            const historyItem = `
                <div class="scan-history-item border-bottom pb-2 mb-2">
                    <div class="d-flex justify-content-between">
                        <strong>${barcode}</strong>
                        <small class="text-muted">${timestamp}</small>
                    </div>
                    <small class="text-muted">Format: ${format}</small>
                </div>
            `;
            
            $('#scanHistory').prepend(historyItem);
            
            // Keep only last 10 items
            $('#scanHistory .scan-history-item').slice(10).remove();
        },

        /**
         * Switch camera
         */
        switchCamera: function() {
            if (this.isScanning) {
                this.stopScanning();
                setTimeout(() => {
                    this.startScanning();
                }, 500);
            }
        },

        /**
         * Update scanner UI state
         */
        updateScannerUI: function(isScanning) {
            if (isScanning) {
                $('#startScanBtn').addClass('d-none');
                $('#stopScanBtn').removeClass('d-none');
                $('#cameraSelect').prop('disabled', true);
            } else {
                $('#stopScanBtn').addClass('d-none');
                $('#startScanBtn').removeClass('d-none');
                $('#cameraSelect').prop('disabled', false);
            }
        },

        /**
         * Update scanner status
         */
        updateScannerStatus: function(message, type = 'info') {
            const $status = $('#scannerStatusText');
            const $container = $status.parent();
            
            $status.text(message);
            
            // Update status styling
            $container.removeClass('bg-dark bg-success bg-danger bg-warning')
                     .addClass(`bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : type === 'warning' ? 'warning' : 'dark'}`);
        },

        /**
         * Cleanup scanner resources
         */
        cleanupScanner: function() {
            this.stopScanning();
            $('#scanHistory').empty();
        },

        /**
         * Play sound effect
         */
        playSound: function(type) {
            if (!this.config.audio.enabled || !this.audioElements[type]) return;
            
            try {
                this.audioElements[type].currentTime = 0;
                this.audioElements[type].play().catch(err => {
                    // Ignore audio play errors (browser policy)
                });
            } catch (err) {
                // Ignore audio errors
            }
        },

        /**
         * Handle barcode input in forms
         */
        handleBarcodeInput: function(event) {
            const $input = $(event.currentTarget);
            const barcode = $input.val().trim();
            
            if (barcode.length >= 8) { // Minimum barcode length
                this.validateBarcode(barcode, $input);
            }
        },

        /**
         * Handle barcode keypress (for barcode scanner guns)
         */
        handleBarcodeKeypress: function(event) {
            // Many barcode scanner guns send Enter after scanning
            if (event.which === 13) {
                const $input = $(event.currentTarget);
                const barcode = $input.val().trim();
                
                if (barcode) {
                    this.lookupProductByBarcode(barcode);
                }
            }
        },

        /**
         * Validate barcode format
         */
        validateBarcode: function(barcode, $input) {
            window.InventoryApp.Ajax.get(this.config.endpoints.validate, { barcode: barcode })
                .done(response => {
                    if (response.valid) {
                        $input.removeClass('is-invalid').addClass('is-valid');
                    } else {
                        $input.removeClass('is-valid').addClass('is-invalid');
                    }
                });
        },

        /**
         * Generate QR code for product
         */
        generateQRCode: function(event) {
            const $btn = $(event.currentTarget);
            const productId = $btn.data('product-id');
            
            if (!productId) {
                window.InventoryApp.Notifications.error('Product ID required for QR code generation');
                return;
            }
            
            window.InventoryApp.Utils.showLoading($btn);
            
            window.InventoryApp.Ajax.get(this.config.endpoints.generate + productId + '/')
                .done(response => {
                    if (response.success) {
                        this.showQRCodeModal(response.qr_code, response.product);
                    } else {
                        window.InventoryApp.Notifications.error('Failed to generate QR code');
                    }
                })
                .always(() => {
                    window.InventoryApp.Utils.hideLoading($btn);
                });
        },

        /**
         * Show QR code modal
         */
        showQRCodeModal: function(qrCodeData, product) {
            const modalHtml = `
                <div class="modal fade" id="qrCodeModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="bi bi-qr-code me-2"></i>QR Code - ${product.name}
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body text-center">
                                <div class="qr-code-container mb-3">
                                    <img src="data:image/png;base64,${qrCodeData}" alt="QR Code" class="img-fluid" style="max-width: 300px;">
                                </div>
                                <h6>${product.name}</h6>
                                <p class="text-muted">SKU: ${product.sku}</p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                    Close
                                </button>
                                <button type="button" class="btn btn-primary" onclick="window.print()">
                                    <i class="bi bi-printer me-1"></i>Print
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove existing modal
            $('#qrCodeModal').remove();
            
            // Add and show new modal
            $('body').append(modalHtml);
            $('#qrCodeModal').modal('show');
        },

        /**
         * Detect barcode scanner gun input
         */
        setupScannerGunDetection: function() {
            let scannerInput = '';
            let scannerTimer = null;
            
            $(document).on('keydown', function(e) {
                // Ignore if focused on input field
                if ($(e.target).is('input, textarea, select')) {
                    return;
                }
                
                // Clear timer
                if (scannerTimer) {
                    clearTimeout(scannerTimer);
                }
                
                // Add character to input
                if (e.key.length === 1) {
                    scannerInput += e.key;
                }
                
                // Set timer to process input
                scannerTimer = setTimeout(() => {
                    if (scannerInput.length >= 8) { // Minimum barcode length
                        // This looks like a barcode scan
                        e.preventDefault();
                        BarcodeScanner.lookupProductByBarcode(scannerInput);
                    }
                    scannerInput = '';
                }, 100);
                
                // Process on Enter
                if (e.which === 13 && scannerInput.length >= 8) {
                    e.preventDefault();
                    clearTimeout(scannerTimer);
                    BarcodeScanner.lookupProductByBarcode(scannerInput);
                    scannerInput = '';
                }
            });
        }
    };

    // Initialize when DOM is ready
    $(document).ready(function() {
        BarcodeScanner.init();
        BarcodeScanner.setupScannerGunDetection();
    });

    // Expose to global scope
    window.InventoryApp = window.InventoryApp || {};
    window.InventoryApp.BarcodeScanner = BarcodeScanner;

})(jQuery);
