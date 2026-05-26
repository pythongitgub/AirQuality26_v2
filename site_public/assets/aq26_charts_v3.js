// AQ26 chart loader v3.5 - defensive Plotly loader
(function(){
  function el(id){ return document.getElementById(id); }
  async function getJSON(path){
    const r = await fetch(path, {cache:'no-store'});
    if(!r.ok) throw new Error(path + ': ' + r.status);
    return await r.json();
  }
  function asArray(x){
    if(Array.isArray(x)) return x;
    if(x === null || x === undefined) return [];
    return [x];
  }
  function asObject(x){ return (x && typeof x === 'object' && !Array.isArray(x)) ? x : {}; }
  function safeLayout(title){
    return {title:title, margin:{t:45,l:45,r:20,b:90}, legend:{orientation:'h'}};
  }
  function lineChart(id, data, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const labels = asArray(data && data.labels);
    const series = asObject(data && data.series);
    const traces = Object.keys(series).map(function(k){
      const y = asArray(series[k]);
      return {x: labels.slice(0, y.length || labels.length), y: y, mode:'lines+markers', name:String(k).replaceAll('_',' '), connectgaps:false};
    }).filter(function(t){ return t.y.length > 0; });
    if(!traces.length){ node.innerHTML = '<p class="aq26-chart-empty">No chart data available yet.</p>'; return; }
    Plotly.newPlot(node, traces, safeLayout(title), {responsive:true, displaylogo:false});
  }
  function barChart(id, obj, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const counts = asObject((obj && (obj.source_type_counts || obj.source_status_counts || obj.counts)) || {});
    const keys = Object.keys(counts);
    if(!keys.length){ node.innerHTML = '<p class="aq26-chart-empty">No chart data available yet.</p>'; return; }
    Plotly.newPlot(node, [{x:keys, y:keys.map(function(k){return counts[k];}), type:'bar'}], safeLayout(title), {responsive:true, displaylogo:false});
  }
  function tableStatus(id, obj, title){
    const node = el(id); if(!node) return;
    const s = obj && obj.summary ? obj.summary : obj;
    if(!s){ node.innerHTML = '<p class="aq26-chart-empty">No provider summary available yet.</p>'; return; }
    const rows = Object.keys(s).filter(function(k){ return typeof s[k] !== 'object'; }).map(function(k){
      return '<tr><th>'+k+'</th><td>'+String(s[k])+'</td></tr>';
    }).join('');
    node.innerHTML = '<h3>'+title+'</h3><table class="aq26-provider-table">'+rows+'</table>';
  }
  async function boot(){
    try { lineChart('aq26-weekly-record-chart', await getJSON('data/charts/weekly_record_counts.json'), 'Weekly source-record quality'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-source-coverage-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Source coverage by week'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-readiness-trend-chart', await getJSON('data/charts/readiness_trend.json'), 'Readiness gates by week'); } catch(e){ console.warn(e); }
    try { barChart('aq26-source-class-chart', await getJSON('data/charts/source_class_summary_latest.json'), 'Latest source classes'); } catch(e){ console.warn(e); }
    try { tableStatus('aq26-laqn-provider-summary', await getJSON('data/providers/laqn/chart_safe/index.json'), 'LAQN provider readiness'); } catch(e){ console.warn(e); }
    try { tableStatus('aq26-earthdata-provider-summary', await getJSON('data/providers/earthdata/summary.json'), 'NASA Earthdata CMR readiness'); } catch(e){ console.warn(e); }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
