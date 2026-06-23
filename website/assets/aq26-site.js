
(function(){
 const btn=document.querySelector('.nav-toggle'); const nav=document.querySelector('#site-nav');
 if(btn&&nav){btn.addEventListener('click',()=>{const open=nav.getAttribute('data-open')==='true';nav.setAttribute('data-open',String(!open));btn.setAttribute('aria-expanded',String(!open));});}
 const y=document.querySelector('[data-year]'); if(y)y.textContent=new Date().getFullYear();
 const q=document.querySelector('[data-filter]'); if(q){q.addEventListener('input',()=>{const term=q.value.toLowerCase();document.querySelectorAll('[data-filter-item]').forEach(el=>{el.style.display=el.textContent.toLowerCase().includes(term)?'':'none';});});}
})();
