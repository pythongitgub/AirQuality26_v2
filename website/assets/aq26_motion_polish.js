
(function(){
  function initMenu(){
    var btn=document.querySelector('[data-aq26-menu]');
    var nav=document.querySelector('.aq26-nav');
    if(!btn||!nav) return;
    btn.addEventListener('click',function(){
      var open=nav.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open?'true':'false');
    });
  }
  function initReadinessSummary(){
    var el=document.querySelector('[data-readiness-json]');
    if(!el) return;
  }
  document.addEventListener('DOMContentLoaded',function(){initMenu();initReadinessSummary();});
})();
