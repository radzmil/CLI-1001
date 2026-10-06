const passwordInput = document.getElementById('password');
const passwordToggle = document.getElementById('toggle-password');
passwordToggle.addEventListener('click', () => {
  const visible = passwordInput.type === 'password';
  passwordInput.type = visible ? 'text' : 'password';
  passwordToggle.setAttribute('aria-pressed', String(visible));
  passwordToggle.setAttribute('aria-label', visible ? 'Sembunyi kata sandi' : 'Tunjuk kata sandi');
  const icon = passwordToggle.querySelector('i, svg');
  if (icon) {
    icon.setAttribute('data-lucide', visible ? 'eye-off' : 'eye');
    if (window.lucide) window.lucide.createIcons();
  }
});
if (window.lucide) window.lucide.createIcons();