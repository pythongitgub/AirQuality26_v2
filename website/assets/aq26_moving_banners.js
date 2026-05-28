(() => {
  const DEFAULT_ITEMS = [
    '46 incinerator / EfW facilities in the register',
    '8 validated monitoring overlays',
    '35 monitoring overlays under review',
    '3 facilities in manual fallback discovery',
    'Newhaven ERF remains the high-confidence reference case',
    'Public pages are redacted; full diagnostics remain protected'
  ];
  function ensureStyles(){
    if(!document.querySelector('link[href*="aq26_moving_banners.css"]')){
      const link=document.createElement('link');
      link.rel='stylesheet';
      link.href='assets/aq26_moving_banners.css?v=aq26-motion-20260528';
      document.head.appendChild(link);
    }
  }
  function bannerExists(){ return document.querySelector('.aq26-moving-banner'); }
  function buildBanner(items){
    const banner=document.createElement('section');
    banner.className='aq26-moving-banner';
    banner.setAttribute('aria-label','AQ26 live evidence highlights');
    const track=document.createElement('div');
    track.className='aq26-moving-banner__track';
    const doubled=[...items,...items];
    doubled.forEach(text=>{
      const item=document.createElement('span');
      item.className='aq26-moving-banner__item';
      item.innerHTML='<span class="aq26-moving-banner__dot" aria-hidden="true"></span><span></span>';
      item.querySelector('span:last-child').textContent=text;
      track.appendChild(item);
    });
    banner.appendChild(track);
    return banner;
  }
  function findHeader(){
    return document.querySelector('header.site-header, header, .aq26-header, nav') || document.body.firstElementChild;
  }
  function findHero(){
    return document.querySelector('.hero, .aq26-hero, .aq26-motion-hero, main section');
  }
  function init(){
    ensureStyles();
    const hero=findHero();
    if(hero) hero.classList.add('aq26-motion-hero');
    document.querySelectorAll('.card,.panel,.stat-card,.aq26-card').forEach(el=>el.classList.add('aq26-pulse-card'));
    if(!bannerExists()){
      const banner=buildBanner(DEFAULT_ITEMS);
      const header=findHeader();
      if(header && header.parentNode){ header.parentNode.insertBefore(banner, header.nextSibling); }
      else { document.body.insertBefore(banner, document.body.firstChild); }
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
