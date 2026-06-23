// AQ26 WeeklyV2 science chart loader V3.3
(function(){
  async function getJSON(path){ const r = await fetch(path, {cache:'no-store'}); if(!r.ok) throw new Error(path+': '+r.status); return r.json(); }
  function el(id){ return document.getElementById(id); }
  function lineChart(id, data, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const labels = data.labels || [];
    const series = data.series || {};
    const traces = Object.keys(series).map(k => ({x: labels, y: series[k], mode:'lines+markers', name:k.replaceAll('_',' '), connectgaps:false}));
    Plotly.newPlot(node, traces, {title:title, margin:{t:45,l:45,r:20,b:80}, legend:{orientation:'h'}}, {responsive:true, displaylogo:false});
  }
  function barChart(id, obj, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const counts = obj.source_type_counts || obj.source_status_counts || {};
    Plotly.newPlot(node, [{x:Object.keys(counts), y:Object.values(counts), type:'bar'}], {title:title, margin:{t:45,l:45,r:20,b:110}}, {responsive:true, displaylogo:false});
  }
  async function boot(){
    try { lineChart('aq26-weekly-record-chart', await getJSON('data/charts/weekly_record_counts.json'), 'Weekly source-record quality'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-source-coverage-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Source coverage by week'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-readiness-trend-chart', await getJSON('data/charts/readiness_trend.json'), 'Readiness gates by week'); } catch(e){ console.warn(e); }
    try { barChart('aq26-source-class-chart', await getJSON('data/charts/source_class_summary_latest.json'), 'Latest source classes'); } catch(e){ console.warn(e); }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
