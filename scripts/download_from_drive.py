#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def load_service_account_info() -> dict:
    raw = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "").strip()

    if not raw:
        raise RuntimeError("Missing GDRIVE_SERVICE_ACCOUNT_JSON secret.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc


def get_drive_service():
    info = load_service_account_info()
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def find_drive_zip(service, folder_id: str, exact_name: str | None) -> dict:
    if exact_name:
        query = (
            f"'{folder_id}' in parents and "
            "trashed=false and "
            "mimeType='application/zip' and "
            f"name='{exact_name}'"
        )
    else:
        query = (
            f"'{folder_id}' in parents and "
            "trashed=false and "
            "mimeType='application/zip' and "
            "name contains 'AirQuality26' and "
            "name contains 'website'"
        )

    response = (
        service.files()
        .list(
            q=query,
            fields="files(id,name,modifiedTime,size,md5Checksum,webViewLink)",
            orderBy="modifiedTime desc",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    files = response.get("files", [])

    if not files:
        raise RuntimeError(
            "No matching website ZIP found in Google Drive. "
            "Check GDRIVE_FOLDER_ID, filename, and Drive folder sharing."
        )

    return files[0]


def download_file(service, file_id: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )

    with output_path.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request, chunksize=1024 * 1024 * 8)
        done = False

        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download progress: {int(status.progress() * 100)}%", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", default=os.environ.get("GDRIVE_FOLDER_ID", "").strip())
    parser.add_argument("--output", default="downloaded/AirQuality26_latest_website.zip")
    parser.add_argument("--drive-zip-name", default=os.environ.get("DRIVE_ZIP_NAME", "").strip())
    args = parser.parse_args()

    if not args.folder_id:
        raise RuntimeError("Missing GDRIVE_FOLDER_ID secret.")

    exact_name = args.drive_zip_name or None

    service = get_drive_service()
    selected = find_drive_zip(service, args.folder_id, exact_name)

    print("Selected Google Drive ZIP:")
    print(json.dumps(selected, indent=2))

    output_path = Path(args.output)
    download_file(service, selected["id"], output_path)

    if not output_path.exists() or output_path.stat().st_size < 1024:
        raise RuntimeError(f"Downloaded ZIP looks invalid or too small: {output_path}")

    print(f"Downloaded to: {output_path}")
    print(f"Size: {output_path.stat().st_size} bytes")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
