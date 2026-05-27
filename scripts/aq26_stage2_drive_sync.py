#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, mimetypes
from pathlib import Path
from typing import Optional
from aq26_common_evidence import write_json, now_utc, file_manifest

def get_secret_json() -> Optional[str]:
    for k in ["GDRIVE_SERVICE_ACCOUNT","GDRIVE_SERVICE_ACCOUNT_JSON","GDRIVE_CREDENTIALS"]:
        v=os.getenv(k,"").strip()
        if v: return v
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--folder-id", default=os.getenv("GDRIVE_FOLDER_ID",""))
    ap.add_argument("--prefix", default="AQ26_STAGE2")
    ap.add_argument("--dry-run", action="store_true")
    args=ap.parse_args()
    src=Path(args.source)
    summary={"status":"warning","generated_utc":now_utc(),"source":str(src),"folder_id_present":bool(args.folder_id),"service_account_present":bool(get_secret_json()),"uploaded":0,"files":file_manifest(src,"drive_sync_source")}
    if args.dry_run:
        summary["status"]="ok"; summary["notes"]="Dry run only; no upload attempted."
        print(json.dumps(summary, indent=2)[:8000]); return
    if not args.folder_id or not get_secret_json():
        summary["notes"]="GDRIVE_FOLDER_ID and GDRIVE_SERVICE_ACCOUNT/GDRIVE_SERVICE_ACCOUNT_JSON/GDRIVE_CREDENTIALS are required."
        print(json.dumps(summary, indent=2)[:8000]); return
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    info=json.loads(get_secret_json())
    creds=service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])
    svc=build("drive","v3",credentials=creds, cache_discovery=False)
    # create timestamp folder
    folder_meta={"name":f"{args.prefix}_{now_utc().replace(':','').replace('-','')}", "mimeType":"application/vnd.google-apps.folder", "parents":[args.folder_id]}
    root=svc.files().create(body=folder_meta, fields="id,name").execute()
    folder_cache={Path("."):root["id"]}
    def ensure_folder(rel_parent: Path):
        if rel_parent in folder_cache: return folder_cache[rel_parent]
        parent_id=ensure_folder(rel_parent.parent)
        meta={"name":rel_parent.name, "mimeType":"application/vnd.google-apps.folder", "parents":[parent_id]}
        res=svc.files().create(body=meta, fields="id").execute()
        folder_cache[rel_parent]=res["id"]
        return res["id"]
    uploaded=[]
    for p in sorted(src.rglob("*")):
        if not p.is_file(): continue
        rel=p.relative_to(src); parent_id=ensure_folder(rel.parent)
        mt=mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        media=MediaFileUpload(str(p), mimetype=mt, resumable=True)
        res=svc.files().create(body={"name":p.name,"parents":[parent_id]}, media_body=media, fields="id,name,size,md5Checksum").execute()
        uploaded.append({"relative_path":str(rel).replace("\\","/"),"drive_file_id":res.get("id"),"name":res.get("name"),"size":res.get("size"),"md5Checksum":res.get("md5Checksum")})
    summary.update({"status":"ok","drive_root_folder_id":root["id"],"uploaded":len(uploaded),"uploaded_files":uploaded[:500]})
    write_json(src/"_gdrive_upload_manifest.json", summary)
    print(json.dumps(summary, indent=2)[:8000])
if __name__=="__main__":
    main()
