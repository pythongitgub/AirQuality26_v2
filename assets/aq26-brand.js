(function () {
  const button = document.querySelector('[data-menu-button]');
  const nav = document.querySelector('#nav');
  if (button && nav) {
    button.addEventListener('click', function () {
      const open = nav.classList.toggle('open');
      button.setAttribute('aria-expanded', String(open));
    });
  }
  function ensureIcon(rel, href, type) {
    if (document.querySelector('link[rel="' + rel + '"][href="' + href + '"]')) return;
    const link = document.createElement('link');
    link.rel = rel;
    link.href = href;
    if (type) link.type = type;
    document.head.appendChild(link);
  }
  ensureIcon('icon', '/assets/favicon.svg', 'image/svg+xml');
  ensureIcon('shortcut icon', '/assets/favicon.svg', 'image/svg+xml');
})();
