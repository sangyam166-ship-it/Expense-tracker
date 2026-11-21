/**
 * FINORA - Core Client Interactions & Controls
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Sidebar Mobile Toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('finora-sidebar');
  const sidebarClose = document.getElementById('sidebar-close');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  if (sidebarClose && sidebar) {
    sidebarClose.addEventListener('click', () => {
      sidebar.classList.remove('mobile-open');
    });
  }

  // Theme Toggle Handler
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('finora-theme', newTheme);

      // Async persist to Django session
      fetch('/profile/toggle-theme/?ajax=1', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).catch(err => console.log('Theme sync error:', err));

      // Refresh charts if present
      if (window.finoraCharts && window.finoraCharts.updateTheme) {
        window.finoraCharts.updateTheme(newTheme);
      }
    });
  }

  // Generic Modal Handlers
  window.openFinoraModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
      if (typeof lucide !== 'undefined') lucide.createIcons();
    }
  };

  window.closeFinoraModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  };

  // Close modals when clicking backdrop
  document.querySelectorAll('.finora-modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
      }
    });
  });

  // Notification Dropdown Toggle
  const notifBtn = document.getElementById('notification-bell-btn');
  const notifDropdown = document.getElementById('notification-dropdown');
  if (notifBtn && notifDropdown) {
    notifBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      notifDropdown.classList.toggle('show');
    });

    document.addEventListener('click', (e) => {
      if (!notifDropdown.contains(e.target) && e.target !== notifBtn) {
        notifDropdown.classList.remove('show');
      }
    });
  }

  // Auto-dismiss alerts after 5 seconds
  document.querySelectorAll('.finora-alert').forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.5s ease';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });
});
