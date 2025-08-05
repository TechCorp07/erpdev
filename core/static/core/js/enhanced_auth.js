// Enhanced JavaScript functionality for BlitzTech Authentication System
class BlitzTechAuth {
    constructor() {
        this.initializeEventListeners();
        this.setupFormValidation();
        this.setupPasswordStrengthMeter();
        this.setupRealTimeValidation();
        this.setupSocialAuth();
        this.loadUserPreferences();
    }

    // Initialize all event listeners
    initializeEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupNotificationHandlers();
            this.setupProfileCompletion();
            this.setupApprovalRequests();
            this.setupSecurityAlerts();
            this.setupAutoSave();
        });
    }

    // Form validation enhancements
    setupFormValidation() {
        const forms = document.querySelectorAll('form[data-validate="true"]');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    this.showValidationErrors(form);
                }
            });

            // Real-time validation for inputs
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('blur', () => {
                    this.validateField(input);
                });

                input.addEventListener('input', () => {
                    this.clearFieldError(input);
                });
            });
        });
    }

    // Password strength meter
    setupPasswordStrengthMeter() {
        const passwordFields = document.querySelectorAll('input[type="password"][data-strength="true"]');
        
        passwordFields.forEach(field => {
            const strengthMeter = this.createPasswordStrengthMeter(field);
            field.parentNode.appendChild(strengthMeter);

            field.addEventListener('input', () => {
                this.updatePasswordStrength(field, strengthMeter);
            });
        });
    }

    createPasswordStrengthMeter(field) {
        const container = document.createElement('div');
        container.className = 'password-strength-meter mt-2';
        container.innerHTML = `
            <div class="password-strength-bar">
                <div class="strength-fill" style="width: 0%"></div>
            </div>
            <div class="strength-text text-muted small mt-1">Enter a password</div>
            <div class="strength-requirements mt-2" style="display: none;">
                <div class="requirement" data-requirement="length">
                    <i class="bi bi-x-circle text-danger"></i>
                    <span>At least 12 characters</span>
                </div>
                <div class="requirement" data-requirement="uppercase">
                    <i class="bi bi-x-circle text-danger"></i>
                    <span>One uppercase letter</span>
                </div>
                <div class="requirement" data-requirement="lowercase">
                    <i class="bi bi-x-circle text-danger"></i>
                    <span>One lowercase letter</span>
                </div>
                <div class="requirement" data-requirement="number">
                    <i class="bi bi-x-circle text-danger"></i>
                    <span>One number</span>
                </div>
                <div class="requirement" data-requirement="special">
                    <i class="bi bi-x-circle text-danger"></i>
                    <span>One special character</span>
                </div>
            </div>
        `;
        return container;
    }

    updatePasswordStrength(field, meter) {
        const password = field.value;
        const requirements = meter.querySelector('.strength-requirements');
        const strengthFill = meter.querySelector('.strength-fill');
        const strengthText = meter.querySelector('.strength-text');
        
        if (password.length === 0) {
            requirements.style.display = 'none';
            strengthFill.style.width = '0%';
            strengthText.textContent = 'Enter a password';
            return;
        }

        requirements.style.display = 'block';
        
        const checks = {
            length: password.length >= 12,
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password),
            number: /\d/.test(password),
            special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)
        };

        let score = 0;
        let strengthClass = '';
        //let strengthText = '';

        // Update requirement indicators
        Object.keys(checks).forEach(requirement => {
            const reqElement = requirements.querySelector(`[data-requirement="${requirement}"]`);
            const icon = reqElement.querySelector('i');
            
            if (checks[requirement]) {
                icon.className = 'bi bi-check-circle text-success';
                score++;
            } else {
                icon.className = 'bi bi-x-circle text-danger';
            }
        });

        // Calculate strength
        const percentage = (score / 5) * 100;
        strengthFill.style.width = `${percentage}%`;

        if (score <= 2) {
            strengthClass = 'bg-danger';
            strengthText = 'Weak';
        } else if (score <= 3) {
            strengthClass = 'bg-warning';
            strengthText = 'Fair';
        } else if (score <= 4) {
            strengthClass = 'bg-info';
            strengthText = 'Good';
        } else {
            strengthClass = 'bg-success';
            strengthText = 'Strong';
        }

        strengthFill.className = `strength-fill ${strengthClass}`;
        meter.querySelector('.strength-text').textContent = strengthText;
    }

    // Real-time field validation
    setupRealTimeValidation() {
        // Username availability check
        const usernameField = document.querySelector('input[name="username"]');
        if (usernameField) {
            let timeout;
            usernameField.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    this.checkUsernameAvailability(usernameField);
                }, 500);
            });
        }

        // Email availability check
        const emailField = document.querySelector('input[name="email"]');
        if (emailField) {
            let timeout;
            emailField.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    this.checkEmailAvailability(emailField);
                }, 500);
            });
        }

        // Phone number formatting
        const phoneFields = document.querySelectorAll('input[name="phone"]');
        phoneFields.forEach(field => {
            field.addEventListener('input', () => {
                this.formatPhoneNumber(field);
            });
        });
    }

    async checkUsernameAvailability(field) {
        const username = field.value.trim();
        if (username.length < 3) return;

        try {
            const response = await fetch(`/auth/api/check-username/?username=${encodeURIComponent(username)}`);
            const data = await response.json();
            
            this.showFieldFeedback(field, data.available, 
                data.available ? 'Username is available' : 'Username is taken');
        } catch (error) {
            console.error('Error checking username:', error);
        }
    }

    async checkEmailAvailability(field) {
        const email = field.value.trim();
        if (!this.isValidEmail(email)) return;

        try {
            const response = await fetch(`/auth/api/check-email/?email=${encodeURIComponent(email)}`);
            const data = await response.json();
            
            this.showFieldFeedback(field, data.available,
                data.available ? 'Email is available' : 'Email is already registered');
        } catch (error) {
            console.error('Error checking email:', error);
        }
    }

    formatPhoneNumber(field) {
        let value = field.value.replace(/\D/g, '');
        
        // Zimbabwe phone number formatting
        if (value.startsWith('263')) {
            value = '+' + value;
        } else if (value.startsWith('0')) {
            value = '+263' + value.substring(1);
        } else if (value.length === 9) {
            value = '+263' + value;
        }
        
        field.value = value;
    }

    showFieldFeedback(field, isValid, message) {
        // Remove existing feedback
        const existingFeedback = field.parentNode.querySelector('.field-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        // Add new feedback
        const feedback = document.createElement('div');
        feedback.className = `field-feedback small mt-1 ${isValid ? 'text-success' : 'text-danger'}`;
        feedback.innerHTML = `<i class="bi bi-${isValid ? 'check-circle' : 'x-circle'} me-1"></i>${message}`;
        
        field.parentNode.appendChild(feedback);
        
        // Update field styling
        field.classList.remove('is-valid', 'is-invalid');
        field.classList.add(isValid ? 'is-valid' : 'is-invalid');
    }

    // Social authentication setup
    setupSocialAuth() {
        const socialButtons = document.querySelectorAll('.social-auth-btn');
        
        socialButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleSocialAuth(button.dataset.provider);
            });
        });
    }

    handleSocialAuth(provider) {
        // Show loading state
        const button = document.querySelector(`[data-provider="${provider}"]`);
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Connecting...';
        button.disabled = true;

        // Redirect to social auth URL
        window.location.href = `/auth/accounts/${provider}/login/`;
    }

    // Notification handling
    setupNotificationHandlers() {
        // Auto-hide notifications after 5 seconds
        const notifications = document.querySelectorAll('.alert:not(.alert-permanent)');
        notifications.forEach(notification => {
            setTimeout(() => {
                this.fadeOut(notification);
            }, 5000);
        });

        // Handle notification actions
        const notificationActions = document.querySelectorAll('[data-notification-action]');
        notificationActions.forEach(action => {
            action.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleNotificationAction(action);
            });
        });

        // Real-time notification updates
        this.setupNotificationPolling();
    }

    setupNotificationPolling() {
        // Poll for new notifications every 30 seconds
        setInterval(async () => {
            try {
                const response = await fetch('/auth/api/notifications/');
                const data = await response.json();
                
                if (data.unread_count > 0) {
                    this.updateNotificationBadge(data.unread_count);
                }
            } catch (error) {
                console.error('Error polling notifications:', error);
            }
        }, 30000);
    }

    updateNotificationBadge(count) {
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'block' : 'none';
        }
    }

    // Profile completion tracking
    setupProfileCompletion() {
        const progressBar = document.querySelector('.profile-progress');
        if (progressBar) {
            this.updateProfileProgress();
        }

        // Track form field completion
        const profileForm = document.querySelector('#profile-completion-form');
        if (profileForm) {
            const requiredFields = profileForm.querySelectorAll('[required]');
            requiredFields.forEach(field => {
                field.addEventListener('input', () => {
                    this.updateProfileProgress();
                });
            });
        }
    }

    async updateProfileProgress() {
        try {
            const response = await fetch('/auth/api/profile-completion-status/');
            const data = await response.json();
            
            const progressBar = document.querySelector('.profile-progress .progress-bar');
            const progressText = document.querySelector('.profile-progress-text');
            
            if (progressBar) {
                progressBar.style.width = `${data.completion_percentage}%`;
            }
            
            if (progressText) {
                progressText.textContent = `${data.completion_percentage}% complete`;
            }

            // Show/hide incomplete field alerts
            this.updateIncompleteFieldsAlert(data.incomplete_fields);
            
        } catch (error) {
            console.error('Error updating profile progress:', error);
        }
    }

    updateIncompleteFieldsAlert(incompleteFields) {
        const alert = document.querySelector('.incomplete-fields-alert');
        if (!alert) return;

        if (incompleteFields.length === 0) {
            alert.style.display = 'none';
        } else {
            alert.style.display = 'block';
            const fieldsList = alert.querySelector('.incomplete-fields-list');
            if (fieldsList) {
                fieldsList.innerHTML = incompleteFields
                    .map(field => `<li>${this.formatFieldName(field)}</li>`)
                    .join('');
            }
        }
    }

    formatFieldName(fieldName) {
        return fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    // Auto-save functionality
    setupAutoSave() {
        const autoSaveForms = document.querySelectorAll('[data-autosave="true"]');
        
        autoSaveForms.forEach(form => {
            let saveTimeout;
            const inputs = form.querySelectorAll('input, select, textarea');
            
            inputs.forEach(input => {
                input.addEventListener('input', () => {
                    clearTimeout(saveTimeout);
                    saveTimeout = setTimeout(() => {
                        this.autoSaveForm(form);
                    }, 2000); // Save after 2 seconds of inactivity
                });
            });
        });
    }

    async autoSaveForm(form) {
        const formData = new FormData(form);
        const saveIndicator = document.querySelector('.auto-save-indicator');
        
        try {
            if (saveIndicator) {
                saveIndicator.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Saving...';
                saveIndicator.className = 'auto-save-indicator text-warning small';
            }

            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (response.ok) {
                if (saveIndicator) {
                    saveIndicator.innerHTML = '<i class="bi bi-check-circle me-1"></i>Saved';
                    saveIndicator.className = 'auto-save-indicator text-success small';
                }
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            if (saveIndicator) {
                saveIndicator.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Save failed';
                saveIndicator.className = 'auto-save-indicator text-danger small';
            }
        }

        // Hide indicator after 3 seconds
        setTimeout(() => {
            if (saveIndicator) {
                saveIndicator.innerHTML = '';
            }
        }, 3000);
    }

    // Security alerts
    setupSecurityAlerts() {
        // Check for suspicious activity
        this.checkSuspiciousActivity();
        
        // Monitor for security events
        window.addEventListener('beforeunload', () => {
            this.logUserActivity('page_unload');
        });

        // Monitor failed login attempts
        const loginForm = document.querySelector('#login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                this.trackLoginAttempt();
            });
        }
    }

    async checkSuspiciousActivity() {
        try {
            const response = await fetch('/auth/api/security-check/');
            const data = await response.json();
            
            if (data.suspicious_activity) {
                this.showSecurityAlert(data.message);
            }
        } catch (error) {
            console.error('Error checking security:', error);
        }
    }

    showSecurityAlert(message) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show position-fixed';
        alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        alert.innerHTML = `
            <i class="bi bi-shield-exclamation me-2"></i>
            <strong>Security Alert:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alert);
    }

    // Utility functions
    validateForm(form) {
        const inputs = form.querySelectorAll('[required]');
        let isValid = true;

        inputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    validateField(field) {
        const value = field.value.trim();
        const fieldType = field.type || field.tagName.toLowerCase();
        let isValid = true;
        let message = '';

        // Required field check
        if (field.hasAttribute('required') && !value) {
            isValid = false;
            message = 'This field is required';
        }

        // Email validation
        if (fieldType === 'email' && value && !this.isValidEmail(value)) {
            isValid = false;
            message = 'Please enter a valid email address';
        }

        // Phone validation
        if (field.name === 'phone' && value && !this.isValidPhone(value)) {
            isValid = false;
            message = 'Please enter a valid Zimbabwe phone number';
        }

        // Password matching
        if (field.name === 'password2') {
            const password1 = document.querySelector('[name="password1"]');
            if (password1 && value !== password1.value) {
                isValid = false;
                message = 'Passwords do not match';
            }
        }

        this.showFieldValidation(field, isValid, message);
        return isValid;
    }

    showFieldValidation(field, isValid, message) {
        field.classList.remove('is-valid', 'is-invalid');
        
        const existingFeedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        if (!isValid && message) {
            field.classList.add('is-invalid');
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = message;
            field.parentNode.appendChild(feedback);
        } else if (isValid && field.value.trim()) {
            field.classList.add('is-valid');
        }
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        const errorFeedback = field.parentNode.querySelector('.invalid-feedback');
        if (errorFeedback) {
            errorFeedback.remove();
        }
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    isValidPhone(phone) {
        const phoneRegex = /^\+263[0-9]{9}$|^0[0-9]{9}$/;
        return phoneRegex.test(phone.replace(/\s/g, ''));
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    fadeOut(element) {
        element.style.opacity = '1';
        element.style.transition = 'opacity 0.5s';
        element.style.opacity = '0';

        setTimeout(() => {
            element.remove();
        }, 500);
    }

    logUserActivity(action) {
        // Log user activity for security monitoring
        fetch('/auth/api/log-activity/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                action: action,
                timestamp: new Date().toISOString()
            })
        }).catch(error => {
            console.error('Error logging activity:', error);
        });
    }

    loadUserPreferences() {
        // Load user theme preference
        const theme = localStorage.getItem('blitztech_theme') || 'light';
        document.documentElement.setAttribute('data-theme', theme);

        // Load other preferences
        const preferences = JSON.parse(localStorage.getItem('blitztech_preferences') || '{}');
        
        if (preferences.notifications_enabled === false) {
            this.disableNotifications();
        }
    }
}

// Enhanced CSS for the authentication system
const authStylesheet = document.createElement('style');
authStylesheet.textContent = `
/* Password Strength Meter */
.password-strength-meter {
    margin-top: 0.5rem;
}

.password-strength-bar {
    height: 4px;
    background-color: #e9ecef;
    border-radius: 2px;
    overflow: hidden;
}

.strength-fill {
    height: 100%;
    transition: all 0.3s ease;
    border-radius: 2px;
}

.strength-requirements {
    margin-top: 0.5rem;
}

.requirement {
    display: flex;
    align-items: center;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
}

.requirement i {
    margin-right: 0.5rem;
    width: 16px;
}

/* Field Validation Feedback */
.field-feedback {
    display: flex;
    align-items: center;
    margin-top: 0.25rem;
}

/* Auto-save Indicator */
.auto-save-indicator {
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 0.25rem;
    padding: 0.5rem 1rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    z-index: 1000;
}

/* Enhanced Form Styling */
.form-control:focus {
    border-color: #0d6efd;
    box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
}

.form-control.is-valid {
    border-color: #198754;
}

.form-control.is-invalid {
    border-color: #dc3545;
}

/* Social Auth Buttons */
.social-auth-btn {
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}

.social-auth-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.social-auth-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

/* Profile Progress */
.profile-progress .progress {
    height: 8px;
    border-radius: 4px;
}

.profile-progress .progress-bar {
    transition: width 0.6s ease;
}

/* Notification Badge */
.notification-badge {
    position: absolute;
    top: -8px;
    right: -8px;
    background: #dc3545;
    color: white;
    border-radius: 50%;
    width: 20px;
    height: 20px;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
}

/* Security Alert Styling */
.alert-warning {
    border-left: 4px solid #ffc107;
}

/* Dark Theme Support */
[data-theme="dark"] {
    --bs-body-bg: #1a1a1a;
    --bs-body-color: #ffffff;
    --bs-primary: #4dabf7;
    --bs-secondary: #6c757d;
    --bs-success: #51cf66;
    --bs-danger: #ff6b6b;
    --bs-warning: #ffd43b;
    --bs-info: #74c0fc;
}

[data-theme="dark"] body {
    background-color: var(--bs-body-bg);
    color: var(--bs-body-color);
}

[data-theme="dark"] .card {
    background-color: #2d2d2d;
    border-color: #404040;
}

[data-theme="dark"] .form-control {
    background-color: #2d2d2d;
    border-color: #404040;
    color: var(--bs-body-color);
}

[data-theme="dark"] .form-control:focus {
    background-color: #2d2d2d;
    border-color: var(--bs-primary);
    color: var(--bs-body-color);
}

/* Mobile Responsive Enhancements */
@media (max-width: 768px) {
    .auto-save-indicator {
        top: 10px;
        right: 10px;
        font-size: 0.875rem;
        padding: 0.25rem 0.5rem;
    }
    
    .social-auth-btn {
        margin-bottom: 0.5rem;
    }
    
    .password-strength-meter {
        font-size: 0.875rem;
    }
}

/* Loading States */
.loading {
    position: relative;
    pointer-events: none;
}

.loading::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 20px;
    height: 20px;
    margin: -10px 0 0 -10px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #0d6efd;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Accessibility Improvements */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

/* Focus indicators for keyboard navigation */
.btn:focus,
.form-control:focus,
.form-check-input:focus {
    outline: 2px solid #0d6efd;
    outline-offset: 2px;
}

/* High contrast mode support */
@media (prefers-contrast: high) {
    .form-control {
        border-width: 2px;
    }
    
    .btn {
        border-width: 2px;
    }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
    .strength-fill,
    .progress-bar,
    .social-auth-btn {
        transition: none;
    }
    
    .loading::after {
        animation: none;
    }
}
`;

document.head.appendChild(authStylesheet);

// Initialize the BlitzTech Auth system when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.blitzTechAuth = new BlitzTechAuth();
});

// API Integration utilities
class BlitzTechAPI {
    constructor() {
        this.baseURL = '/auth/api/';
        this.headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
    }

    async request(endpoint, options = {}) {
        const url = this.baseURL + endpoint;
        const config = {
            headers: { ...this.headers },
            ...options
        };

        // Add CSRF token for POST requests
        if (options.method && options.method !== 'GET') {
            config.headers['X-CSRFToken'] = this.getCSRFToken();
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // Specific API methods
    async checkUsername(username) {
        return this.get(`check-username/?username=${encodeURIComponent(username)}`);
    }

    async checkEmail(email) {
        return this.get(`check-email/?email=${encodeURIComponent(email)}`);
    }

    async getProfileStatus() {
        return this.get('profile-completion-status/');
    }

    async getUserStats() {
        return this.get('user-stats/');
    }

    async logActivity(action, details = {}) {
        return this.post('log-activity/', { action, details });
    }

    async getNotifications() {
        return this.get('notifications/');
    }

    async markNotificationRead(notificationId) {
        return this.post(`notifications/${notificationId}/mark-read/`);
    }
}

// Initialize API client
window.blitzTechAPI = new BlitzTechAPI();