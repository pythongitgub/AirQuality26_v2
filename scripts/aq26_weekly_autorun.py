#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, glob, hashlib, json, os, platform, shutil, subprocess, sys, textwrap, zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "USERNAME", "CDSE", "SMTP")


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def redact_env() -> dict:
    out = {}
    for k, v in sorted(os.environ.items()):
        if any(w in k.upper() for w in SECRET_WORDS):
            if v:
                out[k] = f"SET_REDACTED_len_{len(v)}"
            else:
                out[k] = "EMPTY"
        elif k.startswith("AQ26_") or k in {"GITHUB_RUN_ID", "GITHUB_REPOSITORY", "RUNNER_OS"}:
            out[k] = v
    return out


def load_config(path: Path) -> dict:
    if path.exists() and yaml:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def expand_notebooks(patterns: str) -> list[Path]:
    paths: list[Path] = []
    for pat in [p.strip() for p in patterns.split(",") if p.strip()]:
        paths.extend(Path(p) for p in glob.glob(pat))
    seen, ordered = set(), []
    for p in sorted(paths, key=lambda x: x.name):
        if p.exists() and p.suffix == ".ipynb" and str(p) not in seen:
            ordered.append(p); seen.add(str(p))
    return ordered


def run_cmd(cmd: list[str], log_path: Path, timeout: int = 1800) -> tuple[int, str]:
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return proc.returncode, log_path.read_text(encoding="utf-8", errors="replace")[-6000:]


def file_record(path: Path, role: str, run_root: Path) -> dict:
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(run_root)) if path.is_relative_to(run_root) else str(path),
        "name": path.name,
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/aq26_weekly_report.yml")
    ap.add_argument("--notebook-glob", required=True)
    ap.add_argument("--continue-on-error", default="true")
    ap.add_argument("--output-root", default="outputs/weekly_reports")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    run_ts = utc_ts()
    run_root = Path(args.output_root) / f"AQ26_WEEKLY_{run_ts}"
    executed = run_root / "executed_notebooks"
    html = run_root / "html"
    logs = run_root / "logs"
    tables = run_root / "tables"
    release = run_root / "release"
    for d in (executed, html, logs, tables, release):
        d.mkdir(parents=True, exist_ok=True)

    notebooks = expand_notebooks(args.notebook_glob)
    results = []
    continue_on_error = args.continue_on_error.lower() in {"1", "true", "yes", "y"}

    for nb in notebooks:
        start = datetime.now(timezone.utc).isoformat()
        stem = nb.stem
        out_ipynb = executed / f"{stem}_EXECUTED_{run_ts}.ipynb"
        log_path = logs / f"{stem}_{run_ts}.log"
        cmd = [
            sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", str(nb),
            "--ExecutePreprocessor.kernel_name=python3", "--ExecutePreprocessor.timeout=900",
            "--output", out_ipynb.name, "--output-dir", str(executed),
        ]
        status = "executed"
        error_tail = ""
        try:
            rc, tail = run_cmd(cmd, log_path, timeout=1800)
            if rc != 0:
                status = "failed"; error_tail = tail
        except Exception as e:
            status = "failed"; error_tail = repr(e)
            log_path.write_text(error_tail, encoding="utf-8")
        out_html = ""
        if out_ipynb.exists():
            html_log = logs / f"{stem}_html_{run_ts}.log"
            html_cmd = [sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", str(out_ipynb), "--output", f"{stem}_EXECUTED_{run_ts}.html", "--output-dir", str(html)]
            try:
                run_cmd(html_cmd, html_log, timeout=600)
                candidate = html / f"{stem}_EXECUTED_{run_ts}.html"
                out_html = str(candidate) if candidate.exists() else ""
            except Exception as e:
                error_tail += "\nHTML export failed: " + repr(e)
        results.append({
            "run_ts": run_ts, "notebook": str(nb), "status": status,
            "started_utc": start, "finished_utc": datetime.now(timezone.utc).isoformat(),
            "executed_ipynb": str(out_ipynb) if out_ipynb.exists() else "", "html": out_html,
            "log": str(log_path), "error_tail": error_tail,
        })
        if status == "failed" and not continue_on_error:
            break

    results_csv = tables / f"AQ26_weekly_notebook_results_{run_ts}.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else ["run_ts"])
        w.writeheader(); w.writerows(results)

    records = []
    for p in run_root.rglob("*"):
        if p.is_file():
            role = p.parent.name
            records.append(file_record(p, role, run_root))
    ledger_csv = tables / f"AQ26_weekly_sha256_ledger_{run_ts}.csv"
    with ledger_csv.open("w", newline="", encoding="utf-8") as f:
        fields = ["path", "relative_path", "name", "role", "bytes", "sha256", "mtime_utc"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)

    failed = [r for r in results if r["status"] != "executed"]
    manifest = {
        "run_ts": run_ts,
        "project": cfg.get("project_name", "SCCNEXUS AirQuality26"),
        "controlled_use_boundary": cfg.get("controlled_use_boundary", "Independent review evidence pack; no third-party endorsement implied."),
        "notebook_count": len(notebooks), "executed_count": len(results) - len(failed), "failed_count": len(failed),
        "notebooks": results,
        "environment": {"python": sys.version, "platform": platform.platform(), "env": redact_env()},
        "outputs": {"results_csv": str(results_csv), "sha256_ledger_csv": str(ledger_csv)},
    }
    manifest_path = run_root / f"AQ26_WEEKLY_MASTER_MANIFEST_{run_ts}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report_md = release / f"AQ26_WEEKLY_CONTROLLED_REVIEW_REPORT_{run_ts}.md"
    lines = [
        f"# AQ26 Weekly Controlled Review Report — {run_ts}", "",
        "## Status", "",
        f"- Notebooks discovered: {len(notebooks)}", f"- Executed successfully: {len(results)-len(failed)}", f"- Failed: {len(failed)}", "",
        "## Integrity and provenance", "",
        f"- Master manifest: `{manifest_path}`", f"- SHA256 ledger: `{ledger_csv}`", f"- Notebook results: `{results_csv}`", "",
        "## Controlled-use boundary", "", manifest["controlled_use_boundary"], "",
        "## Failed notebooks", "",
    ]
    if failed:
        for r in failed:
            lines.append(f"- `{Path(r['notebook']).name}` — see `{r['log']}`")
    else:
        lines.append("None.")
    lines += ["", "## Review note", "", "Before sending externally, review failed notebooks, confirm data-source licences, and check that no secret values appear in exported notebooks or logs."]
    report_md.write_text("\n".join(lines), encoding="utf-8")

    zip_path = release / f"AQ26_WEEKLY_VALIDATED_REPORT_BUNDLE_{run_ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in run_root.rglob("*"):
            if p.is_file() and p != zip_path:
                z.write(p, p.relative_to(run_root))
    latest = Path(args.output_root) / "LATEST_RUN.txt"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(str(run_root), encoding="utf-8")
    print(json.dumps({"run_root": str(run_root), "zip": str(zip_path), "failed_count": len(failed)}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
