
(function(){
  const $=(s,root=document)=>root.querySelector(s); const $$=(s,root=document)=>Array.from(root.querySelectorAll(s));
  const nav=$('#nav'); const btn=$('#hamb'); if(btn&&nav){btn.addEventListener('click',()=>nav.classList.toggle('open'));}
  function tryCharts(){ if(!window.Chart || !window.AQ26_DATA) return; const d=window.AQ26_DATA; 
    const counts=d.counts||{}; const dough=$('#chartStatus'); if(dough){new Chart(dough,{type:'doughnut',data:{labels:['Validated','Candidate review','Fallback needed'],datasets:[{data:[counts.validated||0,counts.candidate||0,counts.missing||0]}]},options:{plugins:{legend:{position:'bottom'}}}});} 
    const score=$('#chartScores'); if(score){const bands=d.scoreBands||{};new Chart(score,{type:'bar',data:{labels:Object.keys(bands),datasets:[{label:'Facilities',data:Object.values(bands)}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});}
    const classChart=$('#chartClasses'); if(classChart){const c=d.classCounts||{};new Chart(classChart,{type:'bar',data:{labels:Object.keys(c),datasets:[{label:'Candidates',data:Object.values(c)}]},options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0}}}}});}
    const progress=$('#chartProgress'); if(progress){const p=[counts.validated||0,(counts.validated||0)+(counts.candidate||0),d.total||0];new Chart(progress,{type:'line',data:{labels:['Validated','Overlay path','Register'],datasets:[{label:'Coverage progression',data:p,tension:.35,fill:false}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});}
  }
  function filterTable(){const q=($('#q')?.value||'').toLowerCase();const st=$('#statusFilter')?.value||'';$$('[data-facility-row]').forEach(tr=>{const text=tr.innerText.toLowerCase();const okq=!q||text.includes(q);const oks=!st||tr.dataset.status===st;tr.style.display=(okq&&oks)?'':'none';});}
  $('#q')?.addEventListener('input',filterTable); $('#statusFilter')?.addEventListener('change',filterTable);
  function aiPanel(){const el=$('#aiNarrative'); if(!el||!window.AQ26_DATA) return; const d=window.AQ26_DATA, c=d.counts||{}; const pct=Math.round(((c.validated||0)+(c.candidate||0))*100/(d.total||1)); const unresolved=(c.missing||0); let risk='stable'; if(unresolved>8) risk='needs discovery'; else if(unresolved>0) risk='near-complete'; el.innerHTML='<b>AI-assisted triage:</b> The register currently has an overlay path for '+pct+'% of facilities. Status: <b>'+risk+'</b>. Candidate overlays remain review-only until station role, geography and provenance are confirmed.'; }
  tryCharts(); aiPanel();
})();
