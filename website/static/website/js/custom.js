/**
 * BlitzTech Electronics - Custom JavaScript
 */

// DOM Content Loaded Event
document.addEventListener('DOMContentLoaded', function() {
  // Initialize tooltips
  initTooltips();
  
  // Activate current nav item
  activateNavLink();
  
  // Initialize scroll animations
  initScrollAnimations();
  
  // Portfolio filtering
  initPortfolioFilters();
  
  // Contact form validation
  initContactForm();
  
  // Initialize testimonial carousel if exists
  initTestimonialCarousel();
  
  // Initialize counters
  initCounters();
});

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => 
    new bootstrap.Tooltip(tooltipTriggerEl)
  );
}

/**
 * Activate the current navigation link based on URL
 */
function activateNavLink() {
  const currentLocation = window.location.pathname;
  const navLinks = document.querySelectorAll('.nav-link');
  
  navLinks.forEach(link => {
    if (link.getAttribute('href') === currentLocation) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/**
 * Initialize scroll animations
 */
function initScrollAnimations() {
  const animatedElements = document.querySelectorAll('.animate-on-scroll');
  
  // Check if IntersectionObserver is supported
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animated');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    
    animatedElements.forEach(element => {
      observer.observe(element);
    });
  } else {
    // Fallback for browsers that don't support IntersectionObserver
    animatedElements.forEach(element => {
      element.classList.add('animated');
    });
  }
}

/**
 * Initialize portfolio filters
 */
function initPortfolioFilters() {
  const filterButtons = document.querySelectorAll('[data-filter]');
  const portfolioItems = document.querySelectorAll('.portfolio-item');
  
  if (filterButtons.length) {
    filterButtons.forEach(button => {
      button.addEventListener('click', function() {
        // Remove active class from all buttons
        filterButtons.forEach(btn => btn.classList.remove('active'));
        
        // Add active class to clicked button
        this.classList.add('active');
        
        // Get filter value
        const filterValue = this.getAttribute('data-filter');
        
        // Filter portfolio items
        portfolioItems.forEach(item => {
          const itemCategory = item.getAttribute('data-category');
          
          if (filterValue === 'all' || filterValue === itemCategory) {
            item.style.display = 'block';
            setTimeout(() => {
              item.style.opacity = '1';
              item.style.transform = 'scale(1)';
            }, 50);
          } else {
            item.style.opacity = '0';
            item.style.transform = 'scale(0.8)';
            setTimeout(() => {
              item.style.display = 'none';
            }, 300);
          }
        });
      });
    });
  }
}

/**
 * Initialize contact form validation
 */
function initContactForm() {
  const contactForm = document.getElementById('contactForm');
  
  if (contactForm) {
    contactForm.addEventListener('submit', function(event) {
      if (!contactForm.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      
      contactForm.classList.add('was-validated');
    });
  }
}

/**
 * Smooth scroll to an element
 * @param {string} targetId - The ID of the target element to scroll to
 */
function smoothScrollTo(targetId) {
  const targetElement = document.getElementById(targetId);
  
  if (targetElement) {
    window.scrollTo({
      top: targetElement.offsetTop - 100,
      behavior: 'smooth'
    });
  }
}

/**
 * Toggle mobile menu
 */
function toggleMobileMenu() {
  const navbarCollapse = document.querySelector('.navbar-collapse');
  if (navbarCollapse.classList.contains('show')) {
    navbarCollapse.classList.remove('show');
  } else {
    navbarCollapse.classList.add('show');
  }
}

/**
 * Load more portfolio items
 * This is a demo function for the "Load More" button in the portfolio
 */
function loadMorePortfolio() {
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  const hiddenItems = document.querySelectorAll('.portfolio-item.d-none');
  const itemsToShow = 3;
  let itemsShown = 0;
  
  if (loadMoreBtn && hiddenItems.length) {
    // Show a limited number of hidden items
    hiddenItems.forEach(item => {
      if (itemsShown < itemsToShow) {
        item.classList.remove('d-none');
        item.classList.add('fade-in');
        itemsShown++;
      }
    });
    
    // If all items are now visible, hide the button
    if (document.querySelectorAll('.portfolio-item.d-none').length === 0) {
      loadMoreBtn.style.display = 'none';
    }
  }
}

/**
 * Newsletter subscription
 * This is a demo function for the newsletter subscription form
 */
function subscribeNewsletter(formId) {
  const form = document.getElementById(formId);
  if (form) {
    const email = form.querySelector('input[type="email"]').value;
    const formMessage = form.querySelector('.form-message');
    
    // This would normally be an AJAX request to your server
    if (email && validateEmail(email)) {
      // Successful subscription simulation
      if (formMessage) {
        formMessage.innerHTML = 'Thank you for subscribing!';
        formMessage.classList.add('text-success');
        formMessage.classList.remove('text-danger');
        formMessage.style.display = 'block';
      }
      form.reset();
    } else {
      // Validation error
      if (formMessage) {
        formMessage.innerHTML = 'Please enter a valid email address.';
        formMessage.classList.add('text-danger');
        formMessage.classList.remove('text-success');
        formMessage.style.display = 'block';
      }
    }
  }
  return false; // Prevent form submission
}

/**
 * Validate email format
 * @param {string} email - The email string to validate
 * @return {boolean} - Whether the email is valid
 */
function validateEmail(email) {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
}

/**
 * Initialize testimonial carousel
 */
function initTestimonialCarousel() {
  const testimonialCarousel = document.querySelector('.testimonial-carousel');
  
  if (testimonialCarousel) {
    new bootstrap.Carousel(testimonialCarousel, {
      interval: 5000,
      wrap: true
    });
  }
}

/**
 * Count up animation for statistics
 */
function initCounters() {
  const counters = document.querySelectorAll('.counter-value');
  
  if (counters.length) {
    counters.forEach(counter => {
      const target = parseInt(counter.getAttribute('data-target'));
      const duration = 2000; // 2 seconds
      const step = target / (duration / 16); // 16ms is roughly one frame at 60fps
      let current = 0;
      
      const updateCounter = () => {
        current += step;
        if (current < target) {
          counter.textContent = Math.ceil(current);
          requestAnimationFrame(updateCounter);
        } else {
          counter.textContent = target;
        }
      };
      
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            updateCounter();
            observer.unobserve(entry.target);
          }
        });
      });
      
      observer.observe(counter);
    });
  }
}

/**
 * Initialize product quantity selector for e-commerce
 */
function initQuantitySelector() {
  const decrementBtns = document.querySelectorAll('.quantity-selector .decrement');
  const incrementBtns = document.querySelectorAll('.quantity-selector .increment');
  
  decrementBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const input = this.parentElement.querySelector('input');
      let value = parseInt(input.value);
      if (value > parseInt(input.min || 1)) {
        input.value = value - 1;
        input.dispatchEvent(new Event('change'));
      }
    });
  });
  
  incrementBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const input = this.parentElement.querySelector('input');
      let value = parseInt(input.value);
      const max = parseInt(input.max);
      if (!max || value < max) {
        input.value = value + 1;
        input.dispatchEvent(new Event('change'));
      }
    });
  });
}

/**
 * Initialize FAQ accordion functionality
 */
function initFaqAccordion() {
  // Handle smooth scrolling to FAQ sections
  const faqLinks = document.querySelectorAll('a[href^="#"]');
  
  faqLinks.forEach(link => {
    if (link.getAttribute('href').startsWith('#')) {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        
        const targetId = this.getAttribute('href').substring(1);
        const targetElement = document.getElementById(targetId);
        
        if (targetElement) {
          window.scrollTo({
            top: targetElement.offsetTop - 100,
            behavior: 'smooth'
          });
        }
      });
    }
  });
}

/**
 * Lazy load images
 */
function lazyLoadImages() {
  const lazyImages = document.querySelectorAll('.lazy-image');
  
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.classList.remove('lazy-image');
          imageObserver.unobserve(img);
        }
      });
    });
    
    lazyImages.forEach(img => {
      imageObserver.observe(img);
    });
  } else {
    // Fallback for browsers without IntersectionObserver support
    lazyImages.forEach(img => {
      img.src = img.dataset.src;
      img.classList.remove('lazy-image');
    });
  }
}

/**
 * Initialize search functionality
 */
function initSearch() {
  const searchInput = document.getElementById('searchInput');
  const searchResults = document.getElementById('searchResults');
  
  if (searchInput && searchResults) {
    searchInput.addEventListener('input', function() {
      const searchTerm = this.value.toLowerCase().trim();
      
      if (searchTerm.length > 2) {
        // In a real application, this would be an AJAX request to your server
        // For demo purposes, we'll just show some placeholder results
        searchResults.innerHTML = `
          <div class="list-group">
            <a href="#" class="list-group-item list-group-item-action">
              <div class="d-flex w-100 justify-content-between">
                <h5 class="mb-1">Electronic Components</h5>
                <small>Products</small>
              </div>
              <p class="mb-1">Results matching "${searchTerm}" in components category</p>
            </a>
            <a href="#" class="list-group-item list-group-item-action">
              <div class="d-flex w-100 justify-content-between">
                <h5 class="mb-1">Security Systems</h5>
                <small>Services</small>
              </div>
              <p class="mb-1">Results matching "${searchTerm}" in security category</p>
            </a>
          </div>
        `;
        searchResults.style.display = 'block';
      } else {
        searchResults.style.display = 'none';
      }
    });
    
    // Hide search results when clicking outside
    document.addEventListener('click', function(event) {
      if (!searchInput.contains(event.target) && !searchResults.contains(event.target)) {
        searchResults.style.display = 'none';
      }
    });
  }
}

/**
 * Initialize BlitzTech Electronics specific functionality
 */
function initBlitzTechFeatures() {
  // Initialize all the common features
  initTooltips();
  activateNavLink();
  initScrollAnimations();
  initPortfolioFilters();
  initContactForm();
  initTestimonialCarousel();
  initCounters();
  initQuantitySelector();
  initFaqAccordion();
  lazyLoadImages();
  initSearch();
  
  // Back to top button functionality
  const backToTopBtn = document.getElementById('backToTopBtn');
  if (backToTopBtn) {
    window.addEventListener('scroll', function() {
      if (window.pageYOffset > 300) {
        backToTopBtn.style.display = 'block';
      } else {
        backToTopBtn.style.display = 'none';
      }
    });
    
    backToTopBtn.addEventListener('click', function() {
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  }
}

// Initialize all BlitzTech Electronics features when the DOM is loaded
document.addEventListener('DOMContentLoaded', initBlitzTechFeatures);
