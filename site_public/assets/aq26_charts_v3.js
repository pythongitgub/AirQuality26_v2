
(function(){
  async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return await r.json(); }
  function traces(feed, type){ const labels=feed.labels||[], series=feed.series||{}; return Object.keys(series).map(k=>({x:labels,y:series[k],type:type,mode:type==='scatter'?'lines+markers':undefined,name:k.replaceAll('_',' '),connectgaps:false})); }
  function layout(title){ return {title,margin:{t:45,l:55,r:20,b:70},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}}; }
  async function plot(id,url,type,title,barmode){ const el=document.getElementById(id); if(!el||typeof Plotly==='undefined') return; const feed=await getJSON(url); const lay=layout(title); if(barmode) lay.barmode=barmode; Plotly.react(id,traces(feed,type),lay,{responsive:true}); }
  async function init(){
    try{ await plot('records-chart','data/charts/weekly_record_counts.json','scatter','Weekly evidence records'); }catch(e){console.warn(e);}
    try{ await plot('coverage-chart','data/charts/source_coverage_by_week.json','bar','Source coverage by week','group'); }catch(e){console.warn(e);}
    try{ await plot('readiness-chart','data/charts/readiness_trend.json','scatter','Readiness gates over time'); }catch(e){console.warn(e);}
    try{ await plot('filings-chart','data/charts/source_coverage_by_week.json','bar','Official filings and coverage','stack'); }catch(e){console.warn(e);}
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
