/**
 * Enhanced Dashboard JavaScript with Quote System Integration
 * 
 * This enhanced script provides interactive functionality for the quote-integrated
 * dashboard, including real-time updates, notifications, and user interactions.
 */

// Global dashboard state
window.DashboardApp = {
  config: {
    refreshInterval: 300000, // 5 minutes
    notificationCheckInterval: 60000, // 1 minute
    quickUpdateInterval: 30000, // 30 seconds for quote stats
  },
  state: {
    lastNotificationCheck: Date.now(),
    activeRefreshTimers: [],
    notificationSound: null,
  },
  cache: new Map(),
};

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all dashboard functionality
  initializeDashboard();
  initializeQuoteFeatures();
  initializeNotifications();
  initializeRealTimeUpdates();
  initializeInteractiveElements();
  initializeAccessibility();
});

/**
 * Core dashboard initialization
 */
function initializeDashboard() {
  // Initialize Bootstrap components
  initializeBootstrapComponents();
  
  // Initialize responsive features
  initializeResponsiveFeatures();
  
  // Initialize auto-hide alerts
  initializeAlerts();
  
  // Initialize form enhancements
  initializeFormEnhancements();
  
  // Initialize security features
  initializeSecurityFeatures();
  
  console.log('Dashboard initialized successfully');
}

/**
 * Initialize Bootstrap components (tooltips, popovers, etc.)
 */
function initializeBootstrapComponents() {
  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl, {
      delay: { show: 500, hide: 100 }
    });
  });

  // Initialize popovers
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl, {
      trigger: 'hover focus',
      delay: { show: 300, hide: 100 }
    });
  });

  // Initialize modals with enhanced functionality
  const modalElements = document.querySelectorAll('.modal');
  modalElements.forEach(modal => {
    modal.addEventListener('shown.bs.modal', function() {
      // Focus first input when modal opens
      const firstInput = modal.querySelector('input, textarea, select');
      if (firstInput) {
        firstInput.focus();
      }
    });
  });
}

/**
 * Initialize quote-specific features
 */
function initializeQuoteFeatures() {
  // Quick quote creation from dashboard
  initializeQuickQuoteActions();
  
  // Quote status updates
  initializeQuoteStatusUpdates();
  
  // Quote performance charts
  initializeQuoteCharts();
  
  // Quote attention alerts
  initializeQuoteAttentionAlerts();
  
  // Quote search and filtering
  initializeQuoteFiltering();
  
  console.log('Quote features initialized');
}

/**
 * Initialize quick quote actions
 */
function initializeQuickQuoteActions() {
  // Quick quote creation button
  const quickQuoteBtn = document.getElementById('quickQuoteBtn');
  if (quickQuoteBtn) {
    quickQuoteBtn.addEventListener('click', function() {
      showQuickQuoteModal();
    });
  }

  // Recent clients for quick quote creation
  const clientQuickActions = document.querySelectorAll('.client-quick-quote');
  clientQuickActions.forEach(btn => {
    btn.addEventListener('click', function() {
      const clientId = this.dataset.clientId;
      const clientName = this.dataset.clientName;
      createQuoteForClient(clientId, clientName);
    });
  });

  // Duplicate quote functionality
  const duplicateQuoteBtns = document.querySelectorAll('.duplicate-quote-btn');
  duplicateQuoteBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const quoteId = this.dataset.quoteId;
      duplicateQuote(quoteId);
    });
  });
}

/**
 * Initialize real-time quote status updates
 */
function initializeQuoteStatusUpdates() {
  // Check for quote status changes periodically
  setInterval(updateQuoteStatuses, DashboardApp.config.quickUpdateInterval);
  
  // Handle quote status change notifications
  document.addEventListener('quoteStatusChanged', function(event) {
    const { quoteId, oldStatus, newStatus } = event.detail;
    updateQuoteStatusInUI(quoteId, newStatus);
    
    if (newStatus === 'viewed') {
      showQuoteViewedNotification(quoteId);
    }
  });

  // Refresh quote metrics when quotes are updated
  document.addEventListener('quoteUpdated', function() {
    refreshQuoteMetrics();
  });
}

/**
 * Initialize quote performance charts
 */
function initializeQuoteCharts() {
  // Initialize chart if Chart.js is available and chart container exists
  if (typeof Chart !== 'undefined') {
    const chartContainer = document.getElementById('quotePerformanceChart');
    if (chartContainer) {
      initializeQuotePerformanceChart(chartContainer);
    }

    const monthlyChartContainer = document.getElementById('monthlyQuoteChart');
    if (monthlyChartContainer) {
      initializeMonthlyQuoteChart(monthlyChartContainer);
    }
  }
}

/**
 * Initialize quote attention alerts
 */
function initializeQuoteAttentionAlerts() {
  // Check for quotes needing attention
  checkQuotesNeedingAttention();
  
  // Set up periodic checking
  setInterval(checkQuotesNeedingAttention, DashboardApp.config.refreshInterval);
  
  // Handle attention item interactions
  const attentionItems = document.querySelectorAll('.attention-item');
  attentionItems.forEach(item => {
    item.addEventListener('click', function() {
      const quoteId = this.dataset.quoteId;
      if (quoteId) {
        // Mark as acknowledged and redirect
        acknowledgeAttentionItem(quoteId);
      }
    });
  });
}

/**
 * Initialize enhanced notification system
 */
function initializeNotifications() {
  // Check for new notifications periodically
  setInterval(checkForNewNotifications, DashboardApp.config.notificationCheckInterval);
  
  // Initialize notification sound (if permissions granted)
  initializeNotificationSound();
  
  // Handle notification interactions
  initializeNotificationInteractions();
  
  // Real-time notification updates via WebSocket (if available)
  initializeWebSocketNotifications();
  
  console.log('Notification system initialized');
}

/**
 * Initialize notification interactions
 */
function initializeNotificationInteractions() {
  // Mark notification as read when clicked
  document.addEventListener('click', function(event) {
    const notificationItem = event.target.closest('.notification-item');
    if (notificationItem && notificationItem.classList.contains('unread')) {
      const notificationId = notificationItem.dataset.notificationId;
      if (notificationId) {
        markNotificationAsRead(notificationId, notificationItem);
      }
    }
  });

  // Notification action buttons
  const notificationActions = document.querySelectorAll('.notification-action');
  notificationActions.forEach(btn => {
    btn.addEventListener('click', function(event) {
      event.preventDefault();
      const notificationId = this.dataset.notificationId;
      const actionUrl = this.getAttribute('href');
      
      // Mark as read and then navigate
      markNotificationAsRead(notificationId).then(() => {
        window.location.href = actionUrl;
      });
    });
  });

  // Bulk notification actions
  const markAllReadBtn = document.getElementById('markAllNotificationsRead');
  if (markAllReadBtn) {
    markAllReadBtn.addEventListener('click', function() {
      markAllNotificationsAsRead();
    });
  }
}

/**
 * Initialize real-time updates
 */
function initializeRealTimeUpdates() {
  // Dashboard stats refresh
  const refreshStatsTimer = setInterval(refreshDashboardStats, DashboardApp.config.refreshInterval);
  DashboardApp.state.activeRefreshTimers.push(refreshStatsTimer);
  
  // Quote metrics quick refresh
  const quickRefreshTimer = setInterval(refreshQuoteMetrics, DashboardApp.config.quickUpdateInterval);
  DashboardApp.state.activeRefreshTimers.push(quickRefreshTimer);
  
  // User activity monitoring
  initializeActivityMonitoring();
  
  console.log('Real-time updates initialized');
}

/**
 * Initialize interactive elements
 */
function initializeInteractiveElements() {
  // Sidebar toggle functionality
  initializeSidebarToggle();
  
  // Search functionality
  initializeSearchFeatures();
  
  // Filter functionality
  initializeFilterFeatures();
  
  // Sorting functionality
  initializeSortingFeatures();
  
  // Pagination enhancements
  initializePaginationEnhancements();
  
  // Card interactions
  initializeCardInteractions();
}

/**
 * Initialize accessibility features
 */
function initializeAccessibility() {
  // Keyboard navigation
  initializeKeyboardNavigation();
  
  // Screen reader support
  initializeScreenReaderSupport();
  
  // High contrast mode detection
  initializeHighContrastSupport();
  
  // Focus management
  initializeFocusManagement();
  
  console.log('Accessibility features initialized');
}

/**
 * Refresh dashboard statistics
 */
async function refreshDashboardStats() {
  try {
    const response = await fetch('/auth/api/dashboard-stats/', {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      updateDashboardUI(data);
    }
  } catch (error) {
    console.warn('Failed to refresh dashboard stats:', error);
  }
}

/**
 * Refresh quote metrics specifically
 */
async function refreshQuoteMetrics() {
  try {
    const response = await fetch('/auth/api/quick-quote-stats/', {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      updateQuoteMetricsUI(data);
    }
  } catch (error) {
    console.warn('Failed to refresh quote metrics:', error);
  }
}

/**
 * Check for new notifications
 */
async function checkForNewNotifications() {
  try {
    const response = await fetch('/auth/api/notifications/', {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.new_notifications && data.new_notifications.length > 0) {
        handleNewNotifications(data.new_notifications);
      }
      updateNotificationCount(data.unread_count);
    }
  } catch (error) {
    console.warn('Failed to check notifications:', error);
  }
}

/**
 * Handle new notifications
 */
function handleNewNotifications(notifications) {
  notifications.forEach(notification => {
    showNotificationToast(notification);
    
    // Play sound for important notifications
    if (notification.type === 'quote' || notification.priority === 'high') {
      playNotificationSound();
    }
  });
}

/**
 * Show notification toast
 */
function showNotificationToast(notification) {
  const toastContainer = getOrCreateToastContainer();
  
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <div class="toast-header">
      <i class="bi ${getNotificationIcon(notification.type)} me-2 text-${getNotificationColor(notification.type)}"></i>
      <strong class="me-auto">${notification.title}</strong>
      <small>Just now</small>
      <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
    </div>
    <div class="toast-body">
      ${notification.message}
      ${notification.action_url ? `<div class="mt-2"><a href="${notification.action_url}" class="btn btn-sm btn-primary">${notification.action_text || 'View'}</a></div>` : ''}
    </div>
  `;
  
  toastContainer.appendChild(toast);
  
  const bsToast = new bootstrap.Toast(toast);
  bsToast.show();
  
  // Remove from DOM after hiding
  toast.addEventListener('hidden.bs.toast', () => {
    toast.remove();
  });
}

/**
 * Mark notification as read
 */
async function markNotificationAsRead(notificationId, element = null) {
  try {
    const response = await fetch(`/auth/notifications/mark-read/${notificationId}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
      }
    });
    
    if (response.ok) {
      if (element) {
        element.classList.remove('unread');
        element.classList.add('read');
        
        // Update UI elements
        const newBadge = element.querySelector('.badge.bg-primary');
        if (newBadge && newBadge.textContent === 'New') {
          newBadge.remove();
        }
      }
      
      // Update notification count
      decrementNotificationCount();
      
      return true;
    }
  } catch (error) {
    console.error('Failed to mark notification as read:', error);
    return false;
  }
}

/**
 * Update quote status in UI
 */
function updateQuoteStatusInUI(quoteId, newStatus) {
  const quoteElements = document.querySelectorAll(`[data-quote-id="${quoteId}"]`);
  
  quoteElements.forEach(element => {
    const statusBadge = element.querySelector('.quote-status-badge');
    if (statusBadge) {
      // Remove old status classes
      statusBadge.className = statusBadge.className.replace(/status-\w+/g, '');
      
      // Add new status class
      statusBadge.classList.add(`status-${newStatus}`);
      statusBadge.textContent = newStatus.charAt(0).toUpperCase() + newStatus.slice(1);
      
      // Add animation for status change
      statusBadge.classList.add('success-highlight');
      setTimeout(() => {
        statusBadge.classList.remove('success-highlight');
      }, 1000);
    }
  });
}

/**
 * Initialize sidebar toggle
 */
function initializeSidebarToggle() {
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function() {
      document.body.classList.toggle('sidebar-toggled');
      sidebar.classList.toggle('toggled');
      
      // Save preference
      localStorage.setItem('sidebar-collapsed', sidebar.classList.contains('toggled'));
    });
    
    // Restore sidebar state
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
      document.body.classList.add('sidebar-toggled');
      sidebar.classList.add('toggled');
    }
  }
  
  // Auto-collapse on mobile
  function handleResize() {
    if (window.innerWidth < 768) {
      sidebar?.classList.add('toggled');
    } else {
      const savedState = localStorage.getItem('sidebar-collapsed') === 'true';
      if (!savedState) {
        sidebar?.classList.remove('toggled');
      }
    }
  }
  
  window.addEventListener('resize', handleResize);
  handleResize(); // Initial check
}

/**
 * Initialize form enhancements
 */
function initializeFormEnhancements() {
  // Auto-save functionality
  initializeAutoSave();
  
  // Form validation enhancements
  initializeFormValidation();
  
  // Password visibility toggles
  initializePasswordToggles();
  
  // File upload enhancements
  initializeFileUploads();
}

/**
 * Initialize responsive features
 */
function initializeResponsiveFeatures() {
  // Responsive tables
  const tables = document.querySelectorAll('.table-responsive');
  tables.forEach(table => {
    if (table.scrollWidth > table.clientWidth) {
      table.classList.add('table-responsive-indicator');
    }
  });
  
  // Mobile-friendly card interactions
  if (window.innerWidth < 768) {
    const cards = document.querySelectorAll('.card.hover-effect');
    cards.forEach(card => {
      card.addEventListener('touchstart', function() {
        this.classList.add('card-touched');
      });
    });
  }
}

/**
 * Initialize alerts with auto-hide
 */
function initializeAlerts() {
  const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
  alerts.forEach(alert => {
    // Auto-hide after 5 seconds
    setTimeout(() => {
      const closeButton = alert.querySelector('.btn-close');
      if (closeButton && alert.parentNode) {
        closeButton.click();
      }
    }, 5000);
    
    // Add fade-out animation
    alert.addEventListener('close.bs.alert', function() {
      this.style.transition = 'opacity 0.3s ease';
      this.style.opacity = '0';
    });
  });
}

/**
 * Initialize keyboard navigation
 */
function initializeKeyboardNavigation() {
  document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + / to focus search
    if ((event.ctrlKey || event.metaKey) && event.key === '/') {
      event.preventDefault();
      const searchInput = document.querySelector('input[type="search"], input[name="search"]');
      if (searchInput) {
        searchInput.focus();
      }
    }
    
    // Escape to close modals
    if (event.key === 'Escape') {
      const openModal = document.querySelector('.modal.show');
      if (openModal) {
        const modalInstance = bootstrap.Modal.getInstance(openModal);
        if (modalInstance) {
          modalInstance.hide();
        }
      }
    }
    
    // Ctrl/Cmd + N for new quote (if on quotes page)
    if ((event.ctrlKey || event.metaKey) && event.key === 'n' && window.location.pathname.includes('quotes')) {
      event.preventDefault();
      const newQuoteBtn = document.querySelector('a[href*="quote_create"], #quickQuoteBtn');
      if (newQuoteBtn) {
        newQuoteBtn.click();
      }
    }
  });
}

/**
 * Utility Functions
 */

function getCSRFToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
         document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

function getOrCreateToastContainer() {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.style.zIndex = '1070';
    document.body.appendChild(container);
  }
  return container;
}

function getNotificationIcon(type) {
  const icons = {
    'quote': 'bi-file-earmark-text',
    'success': 'bi-check-circle',
    'warning': 'bi-exclamation-triangle',
    'error': 'bi-x-circle',
    'info': 'bi-info-circle',
    'crm': 'bi-people',
    'system': 'bi-gear'
  };
  return icons[type] || 'bi-bell';
}

function getNotificationColor(type) {
  const colors = {
    'quote': 'primary',
    'success': 'success',
    'warning': 'warning',
    'error': 'danger',
    'info': 'info',
    'crm': 'success',
    'system': 'secondary'
  };
  return colors[type] || 'primary';
}

function updateNotificationCount(count) {
  const badges = document.querySelectorAll('.notification-badge, .nav-link .badge');
  badges.forEach(badge => {
    if (badge.closest('.nav-link[href*="notifications"]') || 
        badge.closest('[href*="notifications"]')) {
      if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline';
        badge.classList.add('bounce-in');
        setTimeout(() => badge.classList.remove('bounce-in'), 500);
      } else {
        badge.style.display = 'none';
      }
    }
  });
}

function decrementNotificationCount() {
  const badges = document.querySelectorAll('.notification-badge, .nav-link .badge');
  badges.forEach(badge => {
    if (badge.closest('.nav-link[href*="notifications"]')) {
      const currentCount = parseInt(badge.textContent) || 0;
      if (currentCount > 1) {
        badge.textContent = currentCount - 1;
      } else {
        badge.style.display = 'none';
      }
    }
  });
}

function playNotificationSound() {
  if (DashboardApp.state.notificationSound) {
    DashboardApp.state.notificationSound.play().catch(() => {
      // Ignore autoplay restrictions
    });
  }
}

function initializeNotificationSound() {
  // Create a subtle notification sound
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    function createNotificationSound() {
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
      oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
      
      gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.2);
    }
    
    DashboardApp.state.notificationSound = { play: createNotificationSound };
  } catch (error) {
    console.log('Audio context not available for notifications');
  }
}

// Performance monitoring
function initializeActivityMonitoring() {
  let lastActivity = Date.now();
  
  ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(event => {
    document.addEventListener(event, () => {
      lastActivity = Date.now();
    }, { passive: true });
  });
  
  // Check for inactivity every minute
  setInterval(() => {
    const inactiveTime = Date.now() - lastActivity;
    if (inactiveTime > 1800000) { // 30 minutes
      console.log('User inactive for 30 minutes');
      // Could implement session warning here
    }
  }, 60000);
}

// Cleanup function for page unload
window.addEventListener('beforeunload', function() {
  // Clear all timers
  DashboardApp.state.activeRefreshTimers.forEach(timer => clearInterval(timer));
  
  // Close any open connections
  // This would be where you'd close WebSocket connections, etc.
});

// Export functions for external use
window.DashboardApp.utils = {
  refreshDashboardStats,
  refreshQuoteMetrics,
  markNotificationAsRead,
  updateQuoteStatusInUI,
  showNotificationToast,
  getCSRFToken
};

console.log('Enhanced Dashboard JavaScript loaded successfully');
