
(function(){
  async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return await r.json(); }
  function plotLine(id, feed, title){
    const el=document.getElementById(id); if(!el || typeof Plotly==='undefined') return;
    const labels=feed.labels||[]; const series=feed.series||{};
    const traces=Object.keys(series).map(k=>({x:labels,y:series[k],type:'scatter',mode:'lines+markers',name:k.replaceAll('_',' ')}));
    Plotly.react(id,traces,{title,margin:{t:45,l:55,r:20,b:55},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}},{responsive:true});
  }
  function plotBar(id, feed, title){
    const el=document.getElementById(id); if(!el || typeof Plotly==='undefined') return;
    const labels=feed.labels||[]; const series=feed.series||{};
    const traces=Object.keys(series).map(k=>({x:labels,y:series[k],type:'bar',name:k.replaceAll('_',' ')}));
    Plotly.react(id,traces,{title,barmode:'group',margin:{t:45,l:55,r:20,b:70},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}},{responsive:true});
  }
  async function init(){
    try { plotLine('records-chart', await getJSON('data/charts/weekly_record_counts.json'), 'Weekly evidence records'); } catch(e){ console.warn(e); }
    try { plotBar('coverage-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Source coverage by week'); } catch(e){ console.warn(e); }
    try { plotLine('readiness-chart', await getJSON('data/charts/readiness_trend.json'), 'Readiness gates over time'); } catch(e){ console.warn(e); }
    try { plotBar('filings-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Official filings and source coverage'); } catch(e){ console.warn(e); }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
