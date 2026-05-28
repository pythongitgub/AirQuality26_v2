
(function(){
  const videos = Array.from(document.querySelectorAll('[data-aq26-banner-video]'));
  videos.forEach((v) => {
    v.addEventListener('error', () => { const box=v.closest('.aq26-video-banner'); if(box) box.classList.add('video-missing'); });
    try { v.play && v.play().catch(()=>{}); } catch(e) {}
  });
})();
