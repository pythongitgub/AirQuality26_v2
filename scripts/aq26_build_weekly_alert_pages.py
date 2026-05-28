#!/usr/bin/env python3
"""
AQ26 weekly Monday alert builder.

Creates redacted and unredacted weekly update pages and injects a public-safe
alert panel into both front pages. Designed to run after the operational site
builder and after any focused/incinerator backfill scripts.

Public output is deliberately legally cautious:
- no causal attribution
- no regulatory breach finding
- no health advice
- candidate overlays remain review-only
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PUBLIC_NOTICE = (
    "AQ26 is an evidence and provenance observatory. Public pages are redacted "
    "and do not make regulatory determinations, legal conclusions, health advice "
    "or causal attribution. Candidate monitoring overlays remain review-only."
)

UNREDACTED_NOTICE = (
    "Internal review area. Contains diagnostics, candidate scores and workflow "
    "status for QA/provenance review. Do not publish raw diagnostics externally."
)

STATUS_LABELS = {
    "validated_existing_overlay": "Validated overlay",
    "candidate_overlay_needs_review": "Candidate under review",
    "no_candidate_selected_yet": "Fallback discovery needed",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x in (None, ""):
            return default
        return int(float(str(x).strip()))
    except Exception:
        return default


def load_overlay_status(repo: Path) -> List[Dict[str, str]]:
    for p in [
        repo / "site_public/data/focus/overlays_v3/facility_overlay_status.csv",
        repo / "site_public/data/focus/overlays_v2/facility_overlay_status.csv",
    ]:
        rows = read_csv(p)
        if rows:
            return rows
    return []


def load_overlay_summary(repo: Path) -> Dict[str, Any]:
    for p in [
        repo / "site_public/data/focus/overlays_v3/incinerator_overlay_summary.json",
        repo / "site_public/data/focus/overlays_v2/incinerator_overlay_summary.json",
    ]:
        data = read_json(p, {})
        if isinstance(data, dict) and data:
            return data
    return {}


def load_backfill_status(repo: Path) -> Dict[str, Any]:
    candidates = [
        repo / ".aq26_weekly_alerts/backfill_status.json",
        repo / "site_public/data/weekly/backfill_status.json",
        repo / "site_public/data/latest_backfill_summary.json",
        repo / "site_public/data/focus/latest_backfill_summary.json",
    ]
    for p in candidates:
        data = read_json(p, {})
        if isinstance(data, dict) and data:
            return data
    return {"status": "not_run_in_this_workflow", "note": "No backfill status JSON found."}


def summarise(rows: List[Dict[str, str]], overlay_summary: Dict[str, Any], backfill_status: Dict[str, Any]) -> Dict[str, Any]:
    counts = Counter(r.get("overlay_status", "") for r in rows)
    total = len(rows) or safe_int(overlay_summary.get("broad_facilities"), 46)
    validated = counts.get("validated_existing_overlay", safe_int(overlay_summary.get("validated_overlays"), 8))
    candidates = counts.get("candidate_overlay_needs_review", safe_int(overlay_summary.get("candidate_facilities_cumulative"), 0))
    unresolved = counts.get("no_candidate_selected_yet", safe_int(overlay_summary.get("no_candidate_selected_yet"), 0))
    high_conf = sum(1 for r in rows if r.get("best_candidate_class") == "high_confidence_official_candidate")
    unresolved_names = [r.get("facility", "") for r in rows if r.get("overlay_status") == "no_candidate_selected_yet"]
    backfill_ok = str(backfill_status.get("status", "")).lower() in {"success", "ok", "completed", "harvested", "not_run_in_this_workflow", "completed_with_script_warnings"}
    if not backfill_ok:
        level = "red"
        headline = "Weekly update needs review"
    elif unresolved > 0 or candidates > 0:
        level = "amber"
        headline = "Weekly incinerator evidence update"
    else:
        level = "green"
        headline = "Weekly update complete"
    coverage_pct = round(((validated + candidates) * 100 / total), 1) if total else 0.0
    return {
        "generated_utc": now_utc(),
        "headline": headline,
        "alert_level": level,
        "total_facilities": total,
        "validated_overlays": validated,
        "candidate_overlays": candidates,
        "unresolved_facilities": unresolved,
        "high_confidence_candidates": high_conf,
        "overlay_path_facilities": validated + candidates,
        "overlay_path_coverage_pct": coverage_pct,
        "unresolved_names": unresolved_names,
        "backfill_status": backfill_status,
        "source_overlay_generated_utc": overlay_summary.get("generated_utc"),
        "public_notice": PUBLIC_NOTICE,
        "unredacted_notice": UNREDACTED_NOTICE,
    }


def weekly_css() -> str:
    return """
.aq26-alert{margin:1rem 0 1.25rem;border-radius:24px;overflow:hidden;border:1px solid #d8e4ef;background:#fff;box-shadow:0 18px 45px rgba(7,26,48,.13)}
.aq26-alert__bar{display:flex;gap:1rem;justify-content:space-between;align-items:center;padding:.85rem 1rem;background:linear-gradient(90deg,#071a30,#0b4d83,#006c67);color:#fff}
.aq26-alert__bar b{letter-spacing:.06em;text-transform:uppercase}.aq26-alert__bar span{opacity:.92}
.aq26-alert__body{display:grid;grid-template-columns:1.6fr 2fr;gap:1rem;padding:1.2rem}
.aq26-alert__body h2{font-size:1.65rem;margin:.1rem 0 .5rem;color:#081d34}.aq26-alert__body p{color:#43556a;line-height:1.55}
.aq26-alert__stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem}.aq26-alert__stat{border:1px solid #e3edf7;border-radius:16px;padding:.85rem;background:#f8fbff}
.aq26-alert__stat .k{font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#66778d}.aq26-alert__stat .v{font-size:1.75rem;font-weight:950;color:#0b2540;margin:.2rem 0}
.aq26-alert__actions{display:flex;gap:.65rem;flex-wrap:wrap;margin-top:.8rem}.aq26-alert__btn{border-radius:999px;padding:.7rem .9rem;background:#0b4d83;color:#fff!important;font-weight:900;text-decoration:none!important}.aq26-alert__btn.alt{background:#edf6ff;color:#0b3154!important;border:1px solid #cfe2f4}
.aq26-alert.amber .aq26-alert__bar{background:linear-gradient(90deg,#071a30,#805a00,#0b4d83)}.aq26-alert.red .aq26-alert__bar{background:linear-gradient(90deg,#071a30,#9b2222,#0b4d83)}.aq26-alert.green .aq26-alert__bar{background:linear-gradient(90deg,#071a30,#177245,#0b4d83)}
.aq26-weekly-ticker{overflow:hidden;border-radius:18px;background:#071a30;color:#fff;margin:1rem 0;white-space:nowrap}.aq26-weekly-ticker__track{display:inline-block;padding:.85rem 0;animation:aq26Ticker 42s linear infinite}.aq26-weekly-ticker span{display:inline-block;margin:0 2rem;font-weight:850}.aq26-weekly-ticker b{color:#f8d169}@keyframes aq26Ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.aq26-video-banner{position:relative;min-height:250px;border-radius:28px;overflow:hidden;margin:1rem 0;background:#071a30;box-shadow:0 18px 45px rgba(7,26,48,.16)}.aq26-video-banner video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.42}.aq26-video-banner__overlay{position:relative;z-index:1;padding:2rem;color:#fff;background:linear-gradient(90deg,rgba(7,26,48,.82),rgba(7,26,48,.2))}.aq26-video-banner__overlay h2{font-size:clamp(1.8rem,4vw,3.6rem);margin:.25rem 0}.aq26-video-banner__overlay p{max-width:780px;line-height:1.55}
@media(max-width:850px){.aq26-alert__body{grid-template-columns:1fr}.aq26-alert__stats{grid-template-columns:repeat(2,minmax(0,1fr))}.aq26-video-banner{min-height:210px}}
@media(prefers-reduced-motion:reduce){.aq26-weekly-ticker__track{animation:none}.aq26-video-banner video{display:none}}
"""


def weekly_js() -> str:
    return """
(function(){
  const videos = Array.from(document.querySelectorAll("[data-aq26-banner-video]"));
  videos.forEach((v) => {
    v.addEventListener("error", () => { const box=v.closest(".aq26-video-banner"); if(box) box.classList.add("video-missing"); });
    try { v.play && v.play().catch(()=>{}); } catch(e){}
  });
})();
"""


def video_banner(summary: Dict[str, Any]) -> str:
    msg = (
        f"{summary['total_facilities']} facilities · {summary['validated_overlays']} validated overlays · "
        f"{summary['candidate_overlays']} candidates under review · {summary['unresolved_facilities']} fallback cases"
    )
    return f"""
<section class="aq26-video-banner" aria-label="AQ26 moving evidence banner">
  <video data-aq26-banner-video autoplay muted loop playsinline preload="metadata">
    <source src="assets/banners/desktop_banner_1.webm" type="video/webm">
  </video>
  <div class="aq26-video-banner__overlay">
    <div class="eyebrow">AQ26 weekly evidence pulse</div>
    <h2>Incinerator evidence update</h2>
    <p>{esc(msg)}. Newhaven remains the validated reference case; raw diagnostics remain in the protected review area.</p>
  </div>
</section>
"""


def ticker(summary: Dict[str, Any]) -> str:
    items = [
        f"<b>{summary['total_facilities']}</b> facilities",
        f"<b>{summary['validated_overlays']}</b> validated overlays",
        f"<b>{summary['candidate_overlays']}</b> candidates under review",
        f"<b>{summary['unresolved_facilities']}</b> fallback cases",
        "Weekly Monday 07:00 UK update",
        "Public-safe redacted alert; full QA in unredacted area",
    ]
    return "<div class='aq26-weekly-ticker'><div class='aq26-weekly-ticker__track'>" + "".join(f"<span>{x}</span>" for x in items * 2) + "</div></div>"


def alert_html(summary: Dict[str, Any], unredacted: bool = False) -> str:
    level = summary.get("alert_level", "amber")
    notice = UNREDACTED_NOTICE if unredacted else PUBLIC_NOTICE
    status = summary.get("backfill_status", {})
    status_txt = status.get("status", "unknown")
    actions = (
        "<a class='aq26-alert__btn' href='weekly-update.html'>Open weekly update</a>"
        "<a class='aq26-alert__btn alt' href='overlays.html'>Overlay status</a>"
    )
    if unredacted:
        actions = (
            "<a class='aq26-alert__btn' href='weekly-update.html'>Open unredacted weekly update</a>"
            "<a class='aq26-alert__btn alt' href='diagnostics.html'>Diagnostics</a>"
            "<a class='aq26-alert__btn alt' href='candidates.html'>Candidates</a>"
        )
    return f"""
<!--AQ26_WEEKLY_ALERT_START-->
<section class="aq26-alert {esc(level)}" role="status" aria-live="polite">
  <div class="aq26-alert__bar"><b>Weekly Monday update</b><span>{esc(summary.get('generated_utc'))} UTC · backfill: {esc(status_txt)}</span></div>
  <div class="aq26-alert__body">
    <div>
      <h2>{esc(summary.get('headline'))}</h2>
      <p>{esc(notice)}</p>
      <div class="aq26-alert__actions">{actions}</div>
    </div>
    <div class="aq26-alert__stats">
      <div class="aq26-alert__stat"><div class="k">Facilities</div><div class="v">{esc(summary['total_facilities'])}</div></div>
      <div class="aq26-alert__stat"><div class="k">Validated</div><div class="v">{esc(summary['validated_overlays'])}</div></div>
      <div class="aq26-alert__stat"><div class="k">Review</div><div class="v">{esc(summary['candidate_overlays'])}</div></div>
      <div class="aq26-alert__stat"><div class="k">Fallback</div><div class="v">{esc(summary['unresolved_facilities'])}</div></div>
    </div>
  </div>
</section>
<!--AQ26_WEEKLY_ALERT_END-->
"""


def basic_page(title: str, body: str, unredacted: bool = False) -> str:
    noindex = "<meta name='robots' content='noindex,nofollow'>" if unredacted else ""
    nav = (
        "<a href='index.html'>Home</a> <a href='weekly-update.html'>Weekly update</a> "
        "<a href='incinerators.html'>Incinerators</a> <a href='overlays.html'>Overlays</a>"
    )
    if unredacted:
        nav = "<a href='index.html'>Dashboard</a> <a href='weekly-update.html'>Weekly update</a> <a href='candidates.html'>Candidates</a> <a href='diagnostics.html'>Diagnostics</a> <a href='../index.html'>Public site</a>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{noindex}<title>{esc(title)} · AQ26</title><link rel="icon" href="assets/favicon.svg?v=aq26-weekly"><link rel="stylesheet" href="assets/aq26_operational.css?v=operational"><link rel="stylesheet" href="assets/aq26_weekly_alerts.css?v=aq26-weekly"></head><body><header class="header"><div class="wrap"><a class="brand" href="index.html"><img src="assets/air_quality_web.svg" alt="SCC Nexus Air Quality Report"></a><nav class="nav open">{nav}</nav></div></header><main class="main">{body}</main><footer class="footer"><div class="wrap"><p>{esc(PUBLIC_NOTICE)}</p></div></footer><script src="assets/aq26_weekly_alerts.js?v=aq26-weekly"></script></body></html>"""


def build_weekly_page(summary: Dict[str, Any], rows: List[Dict[str, str]], unredacted: bool = False) -> str:
    body = video_banner(summary)
    body += ticker(summary)
    body += alert_html(summary, unredacted=unredacted)
    unresolved = ", ".join(summary.get("unresolved_names") or []) or "None"
    body += f"""
<section class="card section">
  <h1>Weekly AQ26 incinerator evidence update</h1>
  <p>This page is regenerated by the Monday 07:00 UK workflow. It summarises the facility overlay state, focused backfill status and review queue.</p>
  <div class="legal"><b>Safety notice:</b> {esc(UNREDACTED_NOTICE if unredacted else PUBLIC_NOTICE)}</div>
</section>
<section class="grid stats">
  <div class="card stat"><div class="label">Facilities</div><div class="value">{esc(summary['total_facilities'])}</div><div class="note">England/Wales register spine</div></div>
  <div class="card stat"><div class="label">Validated</div><div class="value">{esc(summary['validated_overlays'])}</div><div class="note">Retained validated overlays</div></div>
  <div class="card stat"><div class="label">Under review</div><div class="value">{esc(summary['candidate_overlays'])}</div><div class="note">Candidate monitoring overlays</div></div>
  <div class="card stat"><div class="label">Fallback</div><div class="value">{esc(summary['unresolved_facilities'])}</div><div class="note">{esc(unresolved)}</div></div>
</section>
<section class="card section"><h2>AI-assisted triage summary</h2>
<p>The current overlay-path coverage is <b>{esc(summary['overlay_path_coverage_pct'])}%</b>. This is a transparent triage signal based on validated overlays, selected review candidates and unresolved fallback cases. It is not a regulatory or causal conclusion.</p></section>
"""
    body += "<section class='card section'><h2>Facility status table</h2><div class='table-wrap'><table><thead><tr><th>Facility</th><th>Status</th><th>Best site</th><th>Score</th><th>Class</th></tr></thead><tbody>"
    display_rows = rows if unredacted else rows[:46]
    for r in display_rows:
        body += f"<tr><td>{esc(r.get('facility'))}</td><td>{esc(STATUS_LABELS.get(r.get('overlay_status',''), r.get('overlay_status','')))}</td><td>{esc(r.get('best_candidate_site') or '—')}</td><td>{esc(r.get('best_candidate_score') or '—')}</td><td>{esc(r.get('best_candidate_class') or '—')}</td></tr>"
    body += "</tbody></table></div></section>"
    if unredacted:
        body += "<section class='card section'><h2>Unredacted backfill status</h2><pre style='white-space:pre-wrap'>" + esc(json.dumps(summary.get("backfill_status", {}), indent=2)) + "</pre></section>"
    return basic_page("Weekly update", body, unredacted=unredacted)


def ensure_assets(site: Path, repo: Path) -> None:
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "aq26_weekly_alerts.css").write_text(weekly_css(), encoding="utf-8")
    (assets / "aq26_weekly_alerts.js").write_text(weekly_js(), encoding="utf-8")

    for name in ["air_quality_web.svg", "favicon.svg", "logo_web.svg"]:
        for src in [repo / "website/assets" / name, repo / "site_public/assets" / name]:
            if src.exists():
                shutil.copyfile(src, assets / name)
                if name == "favicon.svg":
                    shutil.copyfile(src, site / "favicon.svg")
                break

    for src_dir in [repo / "website/assets/banners", repo / "site_public/assets/banners"]:
        if src_dir.exists():
            dst = assets / "banners"
            dst.mkdir(parents=True, exist_ok=True)
            for p in src_dir.glob("*.webm"):
                shutil.copyfile(p, dst / p.name)


def inject_head_refs(html_text: str) -> str:
    refs = [
        "<link rel=\"icon\" href=\"/favicon.svg?v=aq26-weekly\" type=\"image/svg+xml\">",
        "<link rel=\"icon\" href=\"assets/favicon.svg?v=aq26-weekly\" type=\"image/svg+xml\">",
        "<link rel=\"stylesheet\" href=\"assets/aq26_weekly_alerts.css?v=aq26-weekly\">",
    ]
    for ref in refs:
        key = ref.split("href=\"", 1)[1].split("\"", 1)[0].split("?", 1)[0]
        if key not in html_text:
            html_text = html_text.replace("</head>", ref + "\n</head>")
    if "assets/aq26_weekly_alerts.js" not in html_text:
        html_text = html_text.replace("</body>", "<script src=\"assets/aq26_weekly_alerts.js?v=aq26-weekly\"></script>\n</body>")
    return html_text


def inject_front_page(site: Path, summary: Dict[str, Any], unredacted: bool = False) -> None:
    index = site / "index.html"
    if not index.exists():
        index.write_text(basic_page("AQ26", "", unredacted=unredacted), encoding="utf-8")
    txt = index.read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"<!--AQ26_WEEKLY_ALERT_START-->.*?<!--AQ26_WEEKLY_ALERT_END-->", "", txt, flags=re.S)
    block = video_banner(summary) + ticker(summary) + alert_html(summary, unredacted=unredacted)
    if "<main" in txt:
        txt = re.sub(r"(<main[^>]*>)", r"\1\n" + block, txt, count=1, flags=re.I)
    elif "<body" in txt:
        txt = re.sub(r"(<body[^>]*>)", r"\1\n" + block, txt, count=1, flags=re.I)
    else:
        txt = block + txt
    txt = inject_head_refs(txt)
    index.write_text(txt, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary-out", default="site_public/data/weekly/latest_alert.json")
    ap.add_argument("--unredacted-summary-out", default="site_unredacted/data/weekly/latest_alert_unredacted.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unredacted = repo / args.unredacted_site
    public.mkdir(parents=True, exist_ok=True)
    unredacted.mkdir(parents=True, exist_ok=True)

    rows = load_overlay_status(repo)
    overlay_summary = load_overlay_summary(repo)
    backfill_status = load_backfill_status(repo)
    summary = summarise(rows, overlay_summary, backfill_status)

    for site in [public, unredacted]:
        ensure_assets(site, repo)

    public_summary = dict(summary)
    public_summary.pop("backfill_status", None)
    write_json(repo / args.summary_out, public_summary)
    write_json(repo / args.unredacted_summary_out, summary)

    public.joinpath("weekly-update.html").write_text(build_weekly_page(summary, rows, unredacted=False), encoding="utf-8")
    unredacted.joinpath("weekly-update.html").write_text(build_weekly_page(summary, rows, unredacted=True), encoding="utf-8")

    unredacted.joinpath("robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

    inject_front_page(public, summary, unredacted=False)
    inject_front_page(unredacted, summary, unredacted=True)

    deploy_status = {
        "ok": True,
        "generated_utc": summary["generated_utc"],
        "public_weekly_page": str(public / "weekly-update.html"),
        "unredacted_weekly_page": str(unredacted / "weekly-update.html"),
        "alert_level": summary["alert_level"],
        "counts": {
            "total_facilities": summary["total_facilities"],
            "validated_overlays": summary["validated_overlays"],
            "candidate_overlays": summary["candidate_overlays"],
            "unresolved_facilities": summary["unresolved_facilities"],
        },
    }
    write_json(public / "data/weekly/weekly_alert_build_status.json", deploy_status)
    write_json(unredacted / "data/weekly/weekly_alert_build_status.json", deploy_status)
    print(json.dumps(deploy_status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
