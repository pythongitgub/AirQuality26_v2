#!/usr/bin/env python3
"""Upload AQ26 weekly evidence bundle to Google Drive.

Required secrets:
- GDRIVE_FOLDER_ID
- GDRIVE_SERVICE_ACCOUNT containing the full service-account JSON, not just email.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def as_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    parser.add_argument("--dry-run", default=os.getenv("DRY_RUN", "true"))
    args = parser.parse_args()

    dry_run = as_bool(args.dry_run, True)
    runtime = load_yaml(args.config)
    paths = runtime.get("paths", {})
    evidence = Path(paths.get("evidence", "outputs/evidence"))
    manifest_path = evidence / "latest_bundle_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing bundle manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle = Path(manifest["bundle"])
    if not bundle.exists():
        raise SystemExit(f"Missing bundle file: {bundle}")

    folder_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()
    service_account_raw = os.getenv("GDRIVE_SERVICE_ACCOUNT", "").strip()
    if not folder_id:
        raise SystemExit("GDRIVE_FOLDER_ID secret is missing.")
    if not service_account_raw:
        raise SystemExit("GDRIVE_SERVICE_ACCOUNT secret is missing. It must contain the full JSON.")

    if dry_run:
        print(f"DRY RUN: would upload {bundle} to Google Drive folder {folder_id}.")
        return

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    try:
        service_account_info = json.loads(service_account_raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"GDRIVE_SERVICE_ACCOUNT is not valid JSON: {exc}") from exc

    required = {"type", "project_id", "private_key", "client_email"}
    missing = sorted(required - set(service_account_info))
    if missing:
        raise SystemExit(f"GDRIVE_SERVICE_ACCOUNT JSON missing keys: {missing}")

    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=creds)
    media = MediaFileUpload(str(bundle), mimetype="application/zip", resumable=True)
    metadata = {"name": bundle.name, "parents": [folder_id]}
    created = service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()
    print(json.dumps(created, indent=2))


if __name__ == "__main__":
    main()
