(function(){
  const nav = document.getElementById('nav');
  const btn = document.querySelector('[data-menu-button]');
  if (btn && nav) {
    btn.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  const video = document.querySelector('[data-aq26-hero-video]');
  if (!video) return;

  const cleanPath = window.location.pathname.replace(/\/index\.html$/, '/');
  const bannerRules = [
    [/^\/$/, 'desktop_banner_1.webm'],
    [/^\/newhaven\.html$/, 'desktop_banner_2.webm'],
    [/^\/source-records\.html$/, 'desktop_banner_3.webm'],
    [/^\/weekly-update\.html$/, 'desktop_banner_4.webm'],
    [/^\/archive\.html$/, 'desktop_banner_5.webm'],
    [/^\/methodology\.html$/, 'desktop_banner_6.webm'],
    [/^\/contact\.html$/, 'desktop_banner_2.webm'],
    [/^\/privacy\.html$/, 'desktop_banner_3.webm'],
    [/^\/terms\.html$/, 'desktop_banner_4.webm'],
    [/^\/cookies\.html$/, 'desktop_banner_5.webm'],
    [/^\/accessibility\.html$/, 'desktop_banner_6.webm'],
    [/^\/404\.html$/, 'desktop_banner_1.webm'],

    [/^\/unredacted\/$/, 'desktop_banner_1.webm'],
    [/^\/unredacted\/newhaven\.html$/, 'desktop_banner_2.webm'],
    [/^\/unredacted\/evidence\.html$/, 'desktop_banner_3.webm'],
    [/^\/unredacted\/source-records\.html$/, 'desktop_banner_4.webm'],
    [/^\/unredacted\/weekly-update\.html$/, 'desktop_banner_5.webm'],
    [/^\/unredacted\/history\.html$/, 'desktop_banner_6.webm'],
    [/^\/unredacted\/downloads\.html$/, 'desktop_banner_1.webm'],
    [/^\/unredacted\/diagnostics\.html$/, 'desktop_banner_2.webm'],
    [/^\/unredacted\/candidates\.html$/, 'desktop_banner_3.webm'],
    [/^\/unredacted\/contact\.html$/, 'desktop_banner_4.webm'],
    [/^\/unredacted\/privacy\.html$/, 'desktop_banner_5.webm'],
    [/^\/unredacted\/terms\.html$/, 'desktop_banner_6.webm'],
    [/^\/unredacted\/cookies\.html$/, 'desktop_banner_1.webm'],
    [/^\/unredacted\/accessibility\.html$/, 'desktop_banner_2.webm']
  ];

  const matched = bannerRules.find(([rx]) => rx.test(cleanPath));
  const banner = (video.dataset.banner || (matched ? matched[1] : 'desktop_banner_1.webm'));
  const url = '/assets/' + banner;
  const source = video.querySelector('source');

  // Page-specific banner: no automatic rotation. Each page keeps its assigned video.
  if (source && !source.src.endsWith('/' + banner)) {
    source.src = url;
    video.load();
  }
  video.play().catch(() => {});
})();
