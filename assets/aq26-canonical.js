// AQ26 compatibility script.
// The restored visual site uses aq26-brand.js and AQ26 banner scripts.
(function () {
  function loadScript(src) {
    if (document.querySelector('script[src="' + src + '"]')) return;
    var s = document.createElement('script');
    s.src = src;
    s.defer = true;
    document.head.appendChild(s);
  }
  loadScript('/assets/aq26-brand.js');
  loadScript('/assets/aq26_webm_banners.js');
  loadScript('/assets/aq26_moving_banners.js');
})();
