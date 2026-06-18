
(function(){
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]||c;});}
  function n(v){var x=Number(v||0); return isFinite(x)?x:0;}
  function fmtBytes(v){var b=n(v); if(!b)return '0 B'; var u=['B','KB','MB','GB']; var i=0; while(b>=1024&&i<u.length-1){b/=1024;i++;} return (i?b.toFixed(1):Math.round(b))+' '+u[i];}
  function metric(label,value,note,klass){return '<div class="metric"><span>'+esc(label)+'</span><strong class="'+(klass||'')+'">'+esc(value)+'</strong><p>'+esc(note||'')+'</p></div>';}
  function pending(el,msg){el.innerHTML='<div class="callout"><strong>Evidence lake not packaged yet.</strong><p>'+esc(msg||'Run AQ26 Evidence Lake Package after the LAQN provider run. This is expected on a fresh build.')+'</p></div>';}
  async function load(el){
    var url=el.getAttribute('data-index')||'data/providers/laqn/evidence_lake/latest_index.json';
    try{
      var r=await fetch(url,{cache:'no-store'});
      if(!r.ok){pending(el,'No compact evidence-lake index was found at '+url+'.'); return;}
      var d=await r.json();
      var files=d.files||d.file_manifest||[];
      var run=d.run_ts||d.export_run_ts||d.created_at_utc||'unknown';
      var provider=d.provider||'laqn';
      var counts=d.counts||{};
      var totalFiles=n(counts.total_files||d.total_files||files.length);
      var totalBytes=n(counts.total_bytes||d.total_bytes||files.reduce(function(a,f){return a+n(f.bytes||f.size_bytes);},0));
      var siteReady=n(counts.site_ready_files||files.filter(function(f){return String(f.classification||f.layer||'').toLowerCase().indexOf('site')>=0;}).length);
      var rawFiles=n(counts.raw_files||files.filter(function(f){return String(f.classification||f.layer||'').toLowerCase()==='raw';}).length);
      var manifest=d.manifest_path||d.latest_manifest||d.path||url;
      el.innerHTML='<div class="grid grid-4">'
        + metric('Provider',provider.toUpperCase(),'Current evidence-lake index','ok')
        + metric('Files indexed',totalFiles,'Checksummed files')
        + metric('Total size',fmtBytes(totalBytes),'Drive archive footprint')
        + metric('Site-ready',siteReady,'Lightweight public outputs','ok')
        + '</div><div class="callout" style="margin-top:16px"><strong>Latest export:</strong> '+esc(run)+'<br><strong>Raw files:</strong> '+esc(rawFiles)+' · <strong>Manifest:</strong> <code>'+esc(manifest)+'</code><p>Large raw data remains in Google Drive. The website only exposes compact provenance/status indexes.</p></div>';
    }catch(e){pending(el,'The compact evidence-lake index could not be loaded: '+(e&&e.message?e.message:e));}
  }
  function init(){document.querySelectorAll('#aq26-evidence-lake,[data-aq26-evidence-lake]').forEach(load);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init); else init();
})();
