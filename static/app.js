if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {
  setTimeout(() => form.querySelectorAll('button').forEach(button => { button.disabled = true; }), 0);
}));
