(function(){
  function ready(fn){ if(document.readyState!=='loading') fn(); else document.addEventListener('DOMContentLoaded',fn); }
  ready(function(){
    var btn=document.querySelector('[data-aq26-menu-button]');
    var links=document.querySelector('[data-aq26-links]');
    if(!btn || !links) return;
    btn.addEventListener('click',function(){ var open=links.classList.toggle('open'); btn.setAttribute('aria-expanded', open?'true':'false'); });
  });
})();
