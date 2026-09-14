document.addEventListener('DOMContentLoaded', () => {
  document.body.addEventListener('htmx:beforeRequest', (event) => {
    const target = event.detail?.target;
    if (target) target.classList.add('is-loading');
  });

  document.body.addEventListener('htmx:afterRequest', (event) => {
    const target = event.detail?.target;
    if (target) target.classList.remove('is-loading');
  });

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      const search = document.querySelector('[data-global-search]');
      if (search) {
        event.preventDefault();
        search.focus();
      }
    }
  });
});
