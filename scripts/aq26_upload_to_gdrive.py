#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path


def read_latest(path: Path) -> Path:
    if path.exists():
        p = Path(path.read_text(encoding='utf-8').strip())
        if p.exists():
            return p
    raise FileNotFoundError(f'Latest bundle path not found or invalid: {path}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--latest-path', default='outputs/aq26_production/latest_bundle_path.txt')
    args = ap.parse_args()
    bundle = read_latest(Path(args.latest_path))
    folder_id = os.environ.get('GDRIVE_FOLDER_ID','')
    svc_json = os.environ.get('GDRIVE_SERVICE_ACCOUNT','')
    if not folder_id or not svc_json:
        print('Google Drive upload skipped: GDRIVE_FOLDER_ID or GDRIVE_SERVICE_ACCOUNT is missing.')
        return 0
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = service_account.Credentials.from_service_account_info(json.loads(svc_json), scopes=['https://www.googleapis.com/auth/drive.file'])
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    media = MediaFileUpload(str(bundle), mimetype='application/zip', resumable=True)
    meta = {'name': bundle.name, 'parents': [folder_id], 'description': 'AirQuality26 weekly validated evidence bundle'}
    created = service.files().create(body=meta, media_body=media, fields='id,name,size,createdTime', supportsAllDrives=True).execute()
    print(json.dumps({'uploaded': True, 'name': created.get('name'), 'id_sha256_note': 'file id not printed to avoid leaking share context', 'size': created.get('size')}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
