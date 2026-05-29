(function(){
  const banners = [
    'desktop_banner_1.webm','desktop_banner_2.webm','desktop_banner_3.webm',
    'desktop_banner_4.webm','desktop_banner_5.webm','desktop_banner_6.webm'
  ];
  function pickBanner(){
    const path = location.pathname || 'index';
    let sum = 0; for (let i=0;i<path.length;i++) sum += path.charCodeAt(i);
    return banners[sum % banners.length];
  }
  function assetPath(name){
    const depth = (location.pathname.match(/\//g)||[]).length > 1 ? '../' : '';
    return depth + 'assets/banners/' + name;
  }
  function hydrateVideo(el){
    if (!el || el.dataset.aq26Hydrated === '1') return;
    el.dataset.aq26Hydrated = '1';
    const media = el.querySelector('.aq26-video-banner__media');
    if (!media) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.classList.add('aq26-banner-fallback');
      return;
    }
    const video = document.createElement('video');
    video.autoplay = true; video.muted = true; video.loop = true; video.playsInline = true;
    video.setAttribute('aria-hidden','true');
    const src = document.createElement('source');
    src.src = assetPath(pickBanner()); src.type = 'video/webm';
    video.appendChild(src); media.appendChild(video);
  }
  function init(){
    document.querySelectorAll('.aq26-video-banner').forEach(hydrateVideo);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
