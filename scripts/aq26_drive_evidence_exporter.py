#!/usr/bin/env python3
"""
AQ26 Google Drive evidence-lake exporter.

Purpose
-------
Copies provider outputs from the repository/workflow folder into a controlled
Google Drive evidence lake, preserving provenance with checksums, manifests,
run indexes and a small website-ready status package.

Designed for Google Colab, but it also works anywhere the Drive folder is
mounted as a normal filesystem path.

Example Colab command
---------------------
python scripts/aq26_drive_evidence_exporter.py \
  --repo-root /content/drive/MyDrive/SCC_NEXUS_100GB_ROOT/PROJECTS/AirQuality26/repo/AirQuality26_v2 \
  --drive-root /content/drive/MyDrive/SCC_NEXUS_100GB_ROOT/PROJECTS/AirQuality26 \
  --provider laqn \
  --source-subdir outputs/31_laqn \
  --site-public site_public \
  --copy-mode copy \
  --commit-site-ready
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

RAW_EXTS = {".json", ".xml", ".txt", ".html"}
TABLE_EXTS = {".csv", ".parquet", ".feather", ".xlsx", ".xls"}
SITE_EXTS = {".json", ".csv"}


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def file_md5(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def classify_file(rel: Path) -> str:
    parts = {p.lower() for p in rel.parts}
    suffix = rel.suffix.lower()
    name = rel.name.lower()
    if "chart_safe" in parts or "site_ready" in parts or name.endswith("_chart.json"):
        return "site_ready"
    if suffix in {".parquet", ".feather"}:
        return "derived"
    if suffix in TABLE_EXTS:
        return "interim"
    if suffix in RAW_EXTS:
        return "raw"
    return "interim"


def safe_relpath(path: Path, root: Path) -> Path:
    return Path(os.path.relpath(path, root))


@dataclass
class FileRecord:
    run_ts: str
    provider: str
    stage: str
    source_path: str
    evidence_path: str
    relative_path: str
    size_bytes: int
    sha256: str
    md5: str
    mime_type: str
    copied: bool


def iter_source_files(source_root: Path, include_exts: Optional[set[str]] = None) -> Iterable[Path]:
    for p in source_root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if include_exts and p.suffix.lower() not in include_exts:
            continue
        yield p


def copy_or_link(src: Path, dest: Path, mode: str) -> bool:
    ensure_dir(dest.parent)
    if dest.exists():
        try:
            if dest.stat().st_size == src.stat().st_size and sha256_file(dest) == sha256_file(src):
                return False
        except Exception:
            pass
    if mode == "symlink":
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        os.symlink(src, dest)
    else:
        shutil.copy2(src, dest)
    return True


def write_json(path: Path, obj: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def build_latest_pointer(provider_root: Path, run_ts: str) -> None:
    pointer = {
        "provider": provider_root.name,
        "latest_run_ts": run_ts,
        "latest_run_dir": str(provider_root / "runs" / run_ts),
        "updated_at_utc": iso_now(),
    }
    write_json(provider_root / "latest.json", pointer)


def export_evidence(
    repo_root: Path,
    drive_root: Path,
    provider: str,
    source_subdir: str,
    copy_mode: str,
    site_public: Optional[Path],
    commit_site_ready: bool,
) -> Dict[str, object]:
    run_ts = utc_now_compact()
    source_root = (repo_root / source_subdir).resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"Source folder does not exist: {source_root}")

    evidence_project_root = drive_root.resolve()
    provider_root = evidence_project_root / "data" / "providers" / provider
    run_root = provider_root / "runs" / run_ts
    manifest_root = evidence_project_root / "manifests" / provider

    records: List[FileRecord] = []
    counts_by_stage: Dict[str, int] = {}
    bytes_by_stage: Dict[str, int] = {}

    for src in iter_source_files(source_root):
        rel = safe_relpath(src, source_root)
        stage = classify_file(rel)
        dest = evidence_project_root / "data" / stage / provider / run_ts / rel
        copied = copy_or_link(src, dest, copy_mode)
        size = src.stat().st_size
        rec = FileRecord(
            run_ts=run_ts,
            provider=provider,
            stage=stage,
            source_path=str(src),
            evidence_path=str(dest),
            relative_path=str(rel).replace(os.sep, "/"),
            size_bytes=size,
            sha256=sha256_file(src),
            md5=file_md5(src),
            mime_type=mimetypes.guess_type(src.name)[0] or "application/octet-stream",
            copied=copied,
        )
        records.append(rec)
        counts_by_stage[stage] = counts_by_stage.get(stage, 0) + 1
        bytes_by_stage[stage] = bytes_by_stage.get(stage, 0) + size

    manifest_rows = [asdict(r) for r in records]
    summary = {
        "run_ts": run_ts,
        "updated_at_utc": iso_now(),
        "provider": provider,
        "repo_root": str(repo_root),
        "source_root": str(source_root),
        "drive_root": str(evidence_project_root),
        "total_files": len(records),
        "total_bytes": sum(r.size_bytes for r in records),
        "counts_by_stage": counts_by_stage,
        "bytes_by_stage": bytes_by_stage,
        "stages": ["raw", "interim", "derived", "site_ready"],
        "status": "ok" if records else "warning_no_files",
        "notes": [
            "Google Drive is the evidence lake; GitHub remains the code/orchestration layer.",
            "Raw and derived large files should not be committed to GitHub.",
            "Website should consume only site_ready/chart-safe outputs and this compact index.",
        ],
    }

    write_json(manifest_root / f"manifest_{run_ts}.json", {"summary": summary, "files": manifest_rows})
    write_csv(manifest_root / f"manifest_{run_ts}.csv", manifest_rows)
    write_json(provider_root / "runs" / run_ts / "evidence_export_summary.json", summary)
    build_latest_pointer(provider_root, run_ts)

    # website compact package
    compact = {
        "provider": provider,
        "run_ts": run_ts,
        "updated_at_utc": summary["updated_at_utc"],
        "status": summary["status"],
        "total_files": summary["total_files"],
        "total_bytes": summary["total_bytes"],
        "counts_by_stage": counts_by_stage,
        "manifest_json": str(manifest_root / f"manifest_{run_ts}.json"),
        "manifest_csv": str(manifest_root / f"manifest_{run_ts}.csv"),
        "public_caveat": "This is an evidence-lake export index. Large raw files are stored in Google Drive and are not served directly by the public website.",
    }
    site_ready_drive = evidence_project_root / "site_ready" / "providers" / provider
    write_json(site_ready_drive / "latest_evidence_lake_index.json", compact)

    if commit_site_ready:
        if site_public is None:
            raise ValueError("--commit-site-ready requires --site-public")
        site_dest = site_public / "data" / "providers" / provider / "evidence_lake" / "latest_index.json"
        write_json(site_dest, compact)
        summary["site_ready_repo_index"] = str(site_dest)

    return {"summary": summary, "manifest_rows": len(manifest_rows)}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Export AQ26 provider outputs into a Google Drive evidence lake.")
    p.add_argument("--repo-root", required=True, help="Repository root containing outputs and site_public")
    p.add_argument("--drive-root", required=True, help="Google Drive project root, e.g. .../SCC_NEXUS_100GB_ROOT/PROJECTS/AirQuality26")
    p.add_argument("--provider", default="laqn", help="Provider name, e.g. laqn")
    p.add_argument("--source-subdir", default="outputs/31_laqn", help="Path under repo root to export")
    p.add_argument("--copy-mode", choices=["copy", "symlink"], default="copy")
    p.add_argument("--site-public", default=None, help="site_public folder, defaults to REPO_ROOT/site_public")
    p.add_argument("--commit-site-ready", action="store_true", help="Write compact latest_index.json into site_public for website deployment")
    args = p.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve()
    drive_root = Path(args.drive_root).expanduser().resolve()
    site_public = Path(args.site_public).expanduser().resolve() if args.site_public else repo_root / "site_public"

    result = export_evidence(
        repo_root=repo_root,
        drive_root=drive_root,
        provider=args.provider,
        source_subdir=args.source_subdir,
        copy_mode=args.copy_mode,
        site_public=site_public,
        commit_site_ready=args.commit_site_ready,
    )
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
