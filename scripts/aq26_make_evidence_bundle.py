#!/usr/bin/env python3
"""Create AQ26 weekly evidence bundle ZIPs for public and unredacted areas."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def add_tree(zipf: ZipFile, base: Path, prefix: str) -> int:
    count = 0
    if not base.exists():
        return 0
    for p in sorted(base.rglob("*")):
        if p.is_file():
            zipf.write(p, arcname=str(Path(prefix) / p.relative_to(base)))
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    args = parser.parse_args()

    runtime = load_yaml(args.config)
    paths = runtime.get("paths", {})
    public = Path(paths.get("public_site", "site_public"))
    unredacted = Path(paths.get("unredacted_site", "site_unredacted"))
    reports = Path(paths.get("reports", "outputs/reports"))
    evidence = Path(paths.get("evidence", "outputs/evidence"))
    logs = Path(paths.get("logs", "outputs/logs"))
    downloads_public = Path(paths.get("downloads_public", "site_public/downloads"))
    downloads_unredacted = Path(paths.get("downloads_unredacted", "site_unredacted/downloads"))

    for p in [evidence, logs, downloads_public, downloads_unredacted]:
        ensure_dir(p)

    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    bundle = evidence / f"AQ26_WEEKLY_EVIDENCE_BUNDLE_{now}.zip"

    included = 0
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as zipf:
        included += add_tree(zipf, public, "site_public")
        included += add_tree(zipf, unredacted, "site_unredacted")
        included += add_tree(zipf, reports, "reports")
        included += add_tree(zipf, logs, "logs")
        status = {
            "created_utc": now,
            "included_file_count": included,
            "note": "Operational publishing bundle. Heavy historical science backfill remains in Colab/Drive unless validated outputs are included here.",
        }
        zipf.writestr("BUNDLE_MANIFEST.json", json.dumps(status, indent=2))

    digest = sha256_file(bundle)
    manifest = {
        "bundle": str(bundle),
        "sha256": digest,
        "bytes": bundle.stat().st_size,
        "included_file_count": included,
    }
    (evidence / "latest_bundle_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (logs / "latest_bundle_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    latest_public = downloads_public / "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip"
    latest_public.write_bytes(bundle.read_bytes())
    (downloads_public / "latest-evidence.zip").write_bytes(bundle.read_bytes())
    (downloads_public / "AQ26_WEEKLY_EVIDENCE_BUNDLE.sha256.txt").write_text(f"{digest}  {latest_public.name}\n", encoding="utf-8")

    latest_unredacted = downloads_unredacted / "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip"
    latest_unredacted.write_bytes(bundle.read_bytes())
    (downloads_unredacted / "latest-evidence.zip").write_bytes(bundle.read_bytes())
    (downloads_unredacted / "AQ26_WEEKLY_EVIDENCE_BUNDLE.sha256.txt").write_text(f"{digest}  {latest_unredacted.name}\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
