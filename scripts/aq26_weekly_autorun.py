#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:
    yaml = None

SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "USERNAME", "CDSE", "SMTP", "CLIENT")


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def redact_env() -> dict[str, str]:
    interesting = {}
    for k, v in sorted(os.environ.items()):
        if any(w in k.upper() for w in SECRET_WORDS):
            interesting[k] = f"SET_REDACTED_len_{len(v)}" if v else "EMPTY"
        elif k.startswith("AQ26_") or k.startswith("GITHUB_") or k in {"RUNNER_OS", "RUNNER_ARCH", "CI"}:
            interesting[k] = str(v)
    return interesting


def load_config(path: Path) -> dict[str, Any]:
    if path.exists() and yaml:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def is_executable_notebook(path: Path) -> bool:
    name = path.name.lower()
    bad = ("_executed_", "executed_", ".ipynb_checkpoints", "checkpoint", "autorun", "auto_run", "runner")
    return path.suffix == ".ipynb" and not any(x in str(path).lower() for x in bad)


def expand_notebooks(patterns: str) -> list[Path]:
    paths: list[Path] = []
    for pat in [p.strip() for p in patterns.split(",") if p.strip()]:
        paths.extend(Path(p) for p in glob.glob(pat, recursive=True))
    seen, ordered = set(), []
    for p in sorted(paths, key=lambda x: str(x)):
        if p.exists() and is_executable_notebook(p):
            key = str(p.resolve())
            if key not in seen:
                ordered.append(p); seen.add(key)
    return ordered


def run_cmd(cmd: list[str], log_path: Path, timeout: int = 1800) -> tuple[int, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return proc.returncode, log_path.read_text(encoding="utf-8", errors="replace")[-12000:]


def file_record(path: Path, role: str, run_root: Path) -> dict[str, Any]:
    try:
        rel = str(path.relative_to(run_root))
    except Exception:
        rel = str(path)
    st = path.stat()
    return {
        "path": str(path),
        "relative_path": rel,
        "name": path.name,
        "role": role,
        "bytes": int(st.st_size),
        "sha256": sha256(path),
        "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
    }


def copy_tree_if_exists(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    count = 0
    for p in src.rglob("*"):
        if p.is_file():
            target = dst / p.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            count += 1
    return count


def short(text: Any, width: int = 110) -> str:
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= width else s[: width - 3] + "..."


def make_pdf(path: Path, title: str, lines: list[str]) -> None:
    """Create a simple, dependency-light PDF using reportlab when available; otherwise write a .txt fallback."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except Exception:
        fallback = path.with_suffix(".txt")
        fallback.write_text(title + "\n" + "=" * len(title) + "\n\n" + "\n".join(lines), encoding="utf-8")
        return
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    margin = 16 * mm
    y = height - margin
    c.setTitle(title)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, title[:95])
    y -= 10 * mm
    c.setFont("Helvetica", 8.8)
    for raw in lines:
        wrapped = textwrap.wrap(str(raw), width=105) or [""]
        for line in wrapped:
            if y < margin:
                c.showPage(); y = height - margin; c.setFont("Helvetica", 8.8)
            c.drawString(margin, y, line[:130])
            y -= 4.2 * mm
    c.save()


def discover_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_reports(run_ts: str, cfg: dict[str, Any], run_root: Path, results: list[dict[str, Any]], harvest_manifest: dict[str, Any] | None, ledger_csv: Path, results_csv: Path, manifest_path: Path) -> dict[str, str]:
    release = run_root / "release"
    pdf_dir = release / "pdf"
    release.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    failed = [r for r in results if r.get("status") != "executed"]
    harvest_ok = harvest_manifest.get("ok_count") if isinstance(harvest_manifest, dict) else "not_available"
    harvest_errors = harvest_manifest.get("error_count") if isinstance(harvest_manifest, dict) else "not_available"
    boundary = cfg.get("controlled_use_boundary", "Independent controlled-review pack. No third-party endorsement implied.")

    md = release / f"AQ26_WEEKLY_COMPREHENSIVE_REPORT_{run_ts}.md"
    md_lines = [
        f"# AQ26 Weekly Comprehensive Controlled Review Report — {run_ts}", "",
        "## Certification boundary", "", boundary, "",
        "## Automation status", "",
        f"- Notebooks attempted: {len(results)}",
        f"- Notebooks executed successfully: {len(results) - len(failed)}",
        f"- Notebooks failed: {len(failed)}",
        f"- Live harvest OK source pulls: {harvest_ok}",
        f"- Live harvest errored source pulls: {harvest_errors}", "",
        "## Integrity outputs", "",
        f"- Master manifest: `{manifest_path}`",
        f"- SHA256 ledger: `{ledger_csv}`",
        f"- Notebook results: `{results_csv}`", "",
        "## Review outcome", "",
        "This bundle is suitable for controlled review of automation, provenance and evidence coverage. Scientific or public-health claims require review of source completeness, meteorology, ground-monitor QA, confounders, and site/control comparisons.", "",
        "## Failed notebooks", "",
    ]
    md_lines += ([f"- `{Path(r['notebook']).name}` — see `{r.get('log','')}`" for r in failed] if failed else ["None."])
    md.write_text("\n".join(md_lines), encoding="utf-8")

    exec_pdf = pdf_dir / f"AQ26_EXECUTIVE_REPORT_{run_ts}.pdf"
    make_pdf(exec_pdf, f"AQ26 Executive Weekly Report — {run_ts}", [
        "Certification boundary: " + boundary,
        f"Notebooks attempted: {len(results)}",
        f"Executed successfully: {len(results) - len(failed)}",
        f"Failed: {len(failed)}",
        f"Live harvest OK pulls: {harvest_ok}",
        f"Live harvest error pulls: {harvest_errors}",
        "Status interpretation: automation/provenance can pass even when source completeness is not yet adequate for external scientific claims.",
        "External-use guardrail: do not imply endorsement by WHO, UNEP, EEA, C40 Cities or named experts unless written endorsement is separately obtained.",
    ])

    prov_lines = ["Environment and provenance summary", "", f"Run timestamp UTC: {run_ts}", f"Python: {sys.version.split()[0]}", f"Platform: {platform.platform()}", f"Master manifest: {manifest_path}", f"SHA256 ledger: {ledger_csv}", "", "Redacted environment status:"]
    for k, v in redact_env().items():
        prov_lines.append(f"- {k}: {v}")
    if isinstance(harvest_manifest, dict):
        prov_lines += ["", "Live harvest records:"]
        for rec in harvest_manifest.get("source_records", [])[:160]:
            prov_lines.append(f"- {rec.get('source_name')} | {rec.get('source_type')} | {rec.get('status')} | records={rec.get('record_count')} | {short(rec.get('url'))}")
    prov_pdf = pdf_dir / f"AQ26_PROVENANCE_AND_METADATA_REPORT_{run_ts}.pdf"
    make_pdf(prov_pdf, f"AQ26 Provenance and Metadata Report — {run_ts}", prov_lines)

    nb_lines = ["Notebook execution index", ""]
    for r in results:
        nb_lines.append(f"- {Path(r.get('notebook','')).name} | {r.get('status')} | executed={r.get('executed_ipynb','')} | html={r.get('html','')}")
    nb_pdf = pdf_dir / f"AQ26_NOTEBOOK_EXECUTION_INDEX_{run_ts}.pdf"
    make_pdf(nb_pdf, f"AQ26 Notebook Execution Index — {run_ts}", nb_lines)

    return {"markdown_report": str(md), "executive_pdf": str(exec_pdf), "provenance_pdf": str(prov_pdf), "notebook_index_pdf": str(nb_pdf)}


def main() -> int:
    ap = argparse.ArgumentParser(description="AQ26 weekly comprehensive report autorunner")
    ap.add_argument("--config", default="configs/aq26_weekly_report.yml")
    ap.add_argument("--notebook-glob", required=True)
    ap.add_argument("--continue-on-error", default="true")
    ap.add_argument("--output-root", default="outputs/weekly_reports")
    ap.add_argument("--include-live-harvest", default="outputs/00_live_harvest/LATEST_HARVEST.json")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    ts = utc_ts()
    run_root = Path(args.output_root) / f"AQ26_WEEKLY_{ts}"
    executed = run_root / "executed_notebooks"
    html = run_root / "html"
    logs = run_root / "logs"
    tables = run_root / "tables"
    release = run_root / "release"
    live_copy = run_root / "live_harvest"
    for d in (executed, html, logs, tables, release, live_copy):
        d.mkdir(parents=True, exist_ok=True)

    # Copy the live harvest outputs into the weekly bundle area for a self-contained release.
    copied_live_files = copy_tree_if_exists(Path("outputs/00_live_harvest"), live_copy / "00_live_harvest")
    copied_live_files += copy_tree_if_exists(Path("outputs/03_news_context"), live_copy / "03_news_context")
    copied_live_files += copy_tree_if_exists(Path("outputs/04_ground_aq_providers"), live_copy / "04_ground_aq_providers")
    copied_live_files += copy_tree_if_exists(Path("outputs/05_metoffice_datahub_weather"), live_copy / "05_metoffice_datahub_weather")
    copied_live_files += copy_tree_if_exists(Path("outputs/06_official_filings"), live_copy / "06_official_filings")
    copied_live_files += copy_tree_if_exists(Path("outputs/07_satellite_cdse"), live_copy / "07_satellite_cdse")
    copied_live_files += copy_tree_if_exists(Path("outputs/source_history"), live_copy / "source_history")

    notebooks = expand_notebooks(args.notebook_glob)
    continue_on_error = args.continue_on_error.lower() in {"1", "true", "yes", "y"}
    results: list[dict[str, Any]] = []

    for nb in notebooks:
        start = datetime.now(timezone.utc).isoformat()
        stem = nb.stem
        out_ipynb = executed / f"{stem}_EXECUTED_{ts}.ipynb"
        log_path = logs / f"{stem}_{ts}.log"
        cmd = [
            sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", str(nb),
            "--ExecutePreprocessor.kernel_name=python3", "--ExecutePreprocessor.timeout=1200",
            "--output", out_ipynb.name, "--output-dir", str(executed),
        ]
        status = "executed"; error_tail = ""
        try:
            rc, tail = run_cmd(cmd, log_path, timeout=2400)
            if rc != 0:
                status = "failed"; error_tail = tail
        except Exception as e:
            status = "failed"; error_tail = repr(e)
            log_path.write_text(error_tail, encoding="utf-8")
        out_html = ""
        if out_ipynb.exists():
            html_log = logs / f"{stem}_html_{ts}.log"
            html_cmd = [sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", str(out_ipynb), "--output", f"{stem}_EXECUTED_{ts}.html", "--output-dir", str(html)]
            try:
                run_cmd(html_cmd, html_log, timeout=900)
                candidate = html / f"{stem}_EXECUTED_{ts}.html"
                out_html = str(candidate) if candidate.exists() else ""
            except Exception as e:
                error_tail += "\nHTML export failed: " + repr(e)
        results.append({
            "run_ts": ts,
            "notebook": str(nb),
            "status": status,
            "started_utc": start,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "executed_ipynb": str(out_ipynb) if out_ipynb.exists() else "",
            "html": out_html,
            "log": str(log_path),
            "error_tail": error_tail,
        })
        print(f"{Path(nb).name}: {status}")
        if status == "failed" and not continue_on_error:
            break

    results_csv = tables / f"AQ26_weekly_notebook_results_{ts}.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        fields = list(results[0].keys()) if results else ["run_ts", "status"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(results)

    # First-pass ledger before final reports.
    records = []
    for p in run_root.rglob("*"):
        if p.is_file():
            role = p.parent.name
            records.append(file_record(p, role, run_root))
    ledger_csv = tables / f"AQ26_weekly_sha256_ledger_{ts}.csv"
    with ledger_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["path", "relative_path", "name", "role", "bytes", "sha256", "mtime_utc"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)

    harvest_manifest = discover_json(Path(args.include_live_harvest))
    failed = [r for r in results if r.get("status") != "executed"]
    manifest = {
        "run_ts": ts,
        "project": cfg.get("project_name", "SCCNEXUS AirQuality26"),
        "controlled_use_boundary": cfg.get("controlled_use_boundary", "Independent review evidence pack; no third-party endorsement implied."),
        "notebook_count": len(notebooks),
        "attempted_count": len(results),
        "executed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "copied_live_harvest_files": copied_live_files,
        "live_harvest_manifest_present": harvest_manifest is not None,
        "live_harvest_summary": {k: harvest_manifest.get(k) for k in ["run_ts", "source_record_count", "ok_count", "error_count", "lookback_days"]} if isinstance(harvest_manifest, dict) else {},
        "notebooks": results,
        "environment": {"python": sys.version, "platform": platform.platform(), "env": redact_env()},
        "outputs": {"results_csv": str(results_csv), "sha256_ledger_csv": str(ledger_csv)},
    }
    manifest_path = run_root / f"AQ26_WEEKLY_MASTER_MANIFEST_{ts}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    report_paths = build_reports(ts, cfg, run_root, results, harvest_manifest, ledger_csv, results_csv, manifest_path)
    manifest["report_paths"] = report_paths
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    # Final ledger after reports/manifest exist.
    records = []
    for p in run_root.rglob("*"):
        if p.is_file():
            records.append(file_record(p, p.parent.name, run_root))
    with ledger_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["path", "relative_path", "name", "role", "bytes", "sha256", "mtime_utc"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)

    zip_path = release / f"AQ26_WEEKLY_VALIDATED_REPORT_BUNDLE_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in run_root.rglob("*"):
            if p.is_file() and p != zip_path:
                z.write(p, p.relative_to(run_root))
    zip_sha = sha256(zip_path)
    (release / f"AQ26_WEEKLY_VALIDATED_REPORT_BUNDLE_{ts}.sha256.txt").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")

    latest = Path(args.output_root) / "LATEST_RUN.txt"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(str(run_root), encoding="utf-8")
    print(json.dumps({"run_root": str(run_root), "zip": str(zip_path), "zip_sha256": zip_sha, "failed_count": len(failed), "live_harvest_manifest_present": harvest_manifest is not None}, indent=2))
    return 0 if (not failed or continue_on_error) else 1


if __name__ == "__main__":
    raise SystemExit(main())
