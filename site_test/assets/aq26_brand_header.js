(function () {
  "use strict";

  function pageBase() {
    var path = window.location.pathname || "";
    if (path.indexOf("/unredacted/") !== -1) {
      return "assets/air_quality_web.svg?v=aq26-header-20260527";
    }
    return "assets/air_quality_web.svg?v=aq26-header-20260527";
  }

  function makeBrand() {
    var a = document.createElement("a");
    a.className = "aq26-wide-brand aq26-brand-injected";
    a.href = (window.location.pathname || "").indexOf("/unredacted/") !== -1 ? "index.html" : "index.html";
    a.setAttribute("aria-label", "AQ26 Air Quality Report home");

    var img = document.createElement("img");
    img.className = "aq26-wide-brand-img";
    img.src = pageBase();
    img.alt = "SCC Nexus Air Quality Report";
    img.loading = "eager";
    img.decoding = "async";

    a.appendChild(img);
    return a;
  }

  function existingWideBrand() {
    return document.querySelector(".aq26-wide-brand, img[src*='air_quality_web.svg']");
  }

  function inject() {
    if (existingWideBrand()) return;

    var targets = [
      "header",
      ".site-header",
      ".topbar",
      ".aq26-header",
      ".main-header",
      "nav",
      ".nav",
      ".navbar"
    ];

    var target = null;
    for (var i = 0; i < targets.length; i++) {
      target = document.querySelector(targets[i]);
      if (target) break;
    }

    if (!target) {
      target = document.body;
    }

    var brand = makeBrand();

    // Put the wide brand at the start of the top header/nav area.
    if (target.firstChild) {
      target.insertBefore(brand, target.firstChild);
    } else {
      target.appendChild(brand);
    }

    // Hide obvious old compact logo text block only where it creates duplicate branding.
    var imgs = target.querySelectorAll("img");
    imgs.forEach(function (img) {
      var src = img.getAttribute("src") || "";
      if (src.indexOf("logo_web") !== -1 || src.indexOf("favicon") !== -1) {
        if (!img.classList.contains("aq26-wide-brand-img")) {
          img.classList.add("aq26-old-compact-logo");
          img.style.maxWidth = "0";
          img.style.opacity = "0";
          img.style.margin = "0";
          img.style.pointerEvents = "none";
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();