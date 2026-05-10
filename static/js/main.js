function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const mainWrapper = document.querySelector('.main-wrapper');
  
  if (window.innerWidth <= 768) {
    sidebar.classList.toggle('open');
  } else {
    sidebar.classList.toggle('collapsed');
    if(mainWrapper) mainWrapper.classList.toggle('expanded');
  }
}
// Auto-close flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(f => {
    setTimeout(() => f.remove(), 5000);
  });
});
