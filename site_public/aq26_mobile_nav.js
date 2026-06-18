(function(){
  "use strict";
  const BRAND = "AQ26";
  const SUB = "Air Quality Intelligence";

  function ready(fn){
    if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  function relAssets(){
    const current = document.currentScript && document.currentScript.getAttribute("src");
    if(current && current.includes("/")) return current.replace(/\/[^\/]*$/, "");
    return "assets";
  }

  function uniqueLinks(links){
    const seen = new Set();
    const out = [];
    links.forEach(a => {
      const text = (a.textContent || "").replace(/\s+/g," ").trim();
      const href = a.getAttribute("href") || "";
      if(!text || !href || href === "#" || /^javascript:/i.test(href)) return;
      const key = text.toLowerCase()+"|"+href;
      if(seen.has(key)) return;
      seen.add(key);
      out.push({text, href});
    });
    return out;
  }

  function findNavigationSources(){
    const selectors = [
      "nav",
      "[role='navigation']",
      ".nav-grid",
      ".nav-links",
      ".menu-grid",
      ".menu",
      ".topnav",
      ".tabs",
      ".site-nav",
      "header .links"
    ];
    const sources = [];
    selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if(el.querySelectorAll("a").length >= 2 && !sources.includes(el)) sources.push(el);
      });
    });
    if(!sources.length){
      const header = document.querySelector("header") || document.body;
      if(header.querySelectorAll("a").length >= 2) sources.push(header);
    }
    return sources;
  }

  function buildMobileNav(){
    if(document.querySelector(".aq26-mobile-brandbar")) return;

    const assets = relAssets();
    const skip = document.createElement("a");
    skip.href = "#main";
    skip.className = "aq26-skip-link";
    skip.textContent = "Skip to main content";
    document.body.prepend(skip);

    let main = document.querySelector("main");
    if(main && !main.id) main.id = "main";

    const sources = findNavigationSources();
    sources.forEach(src => src.classList.add("aq26-mobile-nav-source"));

    let links = uniqueLinks(sources.flatMap(src => Array.from(src.querySelectorAll("a"))));
    if(!links.length){
      links = [
        {text:"Observatory", href:"index.html"},
        {text:"Weekly Archive", href:"weekly.html"},
        {text:"Comparisons", href:"comparisons.html"},
        {text:"Source Records", href:"source_records.html"},
        {text:"Readiness", href:"readiness.html"},
        {text:"Methodology", href:"methodology.html"},
        {text:"Downloads", href:"downloads.html"}
      ];
    }

    const bar = document.createElement("div");
    bar.className = "aq26-mobile-brandbar";
    bar.innerHTML = `
      <div style="display:flex;align-items:center;gap:.65rem;min-width:0">
        <img src="${assets}/logo_web.svg" alt="AQ26 logo" loading="lazy">
        <div><strong>${BRAND}</strong><small>${SUB}</small></div>
      </div>
      <button class="aq26-mobile-menu-toggle" type="button" aria-expanded="false" aria-controls="aq26-mobile-menu-panel">
        <span class="aq26-burger" aria-hidden="true"><span></span><span></span><span></span></span>
        <span>Menu</span>
      </button>
    `;

    const panel = document.createElement("div");
    panel.className = "aq26-mobile-menu-panel";
    panel.id = "aq26-mobile-menu-panel";
    panel.setAttribute("hidden", "");
    links.forEach(l => {
      const a = document.createElement("a");
      a.href = l.href;
      a.textContent = l.text;
      panel.appendChild(a);
    });

    document.body.prepend(panel);
    document.body.prepend(bar);

    const btn = bar.querySelector("button");
    btn.addEventListener("click", () => {
      const open = !document.body.classList.contains("aq26-nav-open");
      document.body.classList.toggle("aq26-nav-open", open);
      btn.setAttribute("aria-expanded", String(open));
      if(open) panel.removeAttribute("hidden"); else panel.setAttribute("hidden", "");
    });

    panel.addEventListener("click", (ev) => {
      if(ev.target && ev.target.tagName === "A"){
        document.body.classList.remove("aq26-nav-open");
        btn.setAttribute("aria-expanded","false");
        panel.setAttribute("hidden","");
      }
    });
  }

  ready(buildMobileNav);
})();
