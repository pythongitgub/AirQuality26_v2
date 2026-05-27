(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  ready(function(){
    var header = document.querySelector('header.site-header, .site-header, .aq26-header, header');
    if(!header) return;
    header.classList.add('aq26-white-header');
    var nav = header.querySelector('nav, .site-nav, .aq26-nav');
    if(nav) nav.classList.add('aq26-nav');
    // Replace visible compact-icon logos in headers with full SCC Nexus Air Quality Report SVG.
    var logoCandidates = header.querySelectorAll('img');
    logoCandidates.forEach(function(img){
      var src = img.getAttribute('src') || '';
      if(src.indexOf('favicon') !== -1 || src.indexOf('logo') !== -1 || src.indexOf('air_quality_web') !== -1){
        img.setAttribute('src', 'assets/air_quality_web.svg?v=aq26-legibility-20260527');
        img.setAttribute('alt', 'SCC Nexus Air Quality Report');
        img.classList.add('aq26-header-logo');
      }
    });
    if(!header.querySelector('img.aq26-header-logo')){
      var brand = header.querySelector('a, .brand, .site-brand') || header;
      var img = document.createElement('img');
      img.src = 'assets/air_quality_web.svg?v=aq26-legibility-20260527';
      img.alt = 'SCC Nexus Air Quality Report';
      img.className = 'aq26-header-logo';
      brand.insertBefore(img, brand.firstChild);
    }
    if(nav && !header.querySelector('.aq26-mobile-toggle')){
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'aq26-mobile-toggle';
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = 'Menu';
      btn.addEventListener('click', function(){
        var open = document.body.classList.toggle('aq26-menu-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      nav.parentNode.insertBefore(btn, nav);
    }
  });
})();
