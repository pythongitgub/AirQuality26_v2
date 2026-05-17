#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os
from collections import deque
from pathlib import Path
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account=None; build=None

def env_first(*names):
    for n in names:
        v=os.getenv(n,'')
        if v: return v.strip()
    return ''
def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()
def write_json(p,obj):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding='utf-8'); return p

def make_service():
    if service_account is None or build is None: raise RuntimeError('google api packages not installed')
    cred_text=env_first('GDRIVE_SERVICE_ACCOUNT','GDRIVE_SERVICE_ACCOUNT_JSON','GDRIVE_CREDENTIALS')
    if not cred_text: raise RuntimeError('no service account JSON secret')
    info=json.loads(cred_text)
    creds=service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive','v3',credentials=creds,cache_discovery=False), info.get('client_email','')

def list_children(svc, folder_id):
    rows=[]; token=None
    fields='nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,webViewLink,parents,shortcutDetails)'
    while True:
        resp=svc.files().list(q=f"'{folder_id}' in parents and trashed=false", fields=fields, pageSize=1000, pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        rows += resp.get('files',[]); token=resp.get('nextPageToken')
        if not token: break
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',default='outputs'); ap.add_argument('--folder-id',default=''); ap.add_argument('--max-files',type=int,default=5000); ap.add_argument('--max-depth',type=int,default=7); args=ap.parse_args()
    out=Path(args.output_root)/'08_gdrive_snapshot'; out.mkdir(parents=True, exist_ok=True)
    folder_id=args.folder_id.strip() or os.getenv('GDRIVE_FOLDER_ID','').strip()
    result={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'folder_id_hash':sha_text(folder_id)[:12] if folder_id else '', 'status':'unknown','service_account_email_present':False,'max_files':args.max_files,'max_depth':args.max_depth,'file_count':0,'folder_count':0,'files':[],'errors':[]}
    if not folder_id:
        result['status']='skipped_no_folder_id'; write_json(out/'gdrive_recursive_inventory.json',result); print(json.dumps(result,indent=2)); return
    try:
        svc,email=make_service(); result['service_account_email_present']=bool(email)
        q=deque([(folder_id,'ROOT',0)]); seen=set()
        while q and len(result['files'])<args.max_files:
            fid,path,depth=q.popleft()
            if fid in seen or depth>args.max_depth: continue
            seen.add(fid)
            try: children=list_children(svc,fid)
            except Exception as e: result['errors'].append({'path':path,'folder_id_hash':sha_text(fid)[:12],'error':repr(e)}); continue
            for item in children:
                p=f"{path}/{item.get('name','')}"; mime=item.get('mimeType'); is_folder=mime=='application/vnd.google-apps.folder'; is_shortcut=mime=='application/vnd.google-apps.shortcut'
                result['files'].append({'path':p,'id_hash':sha_text(item.get('id',''))[:12],'name':item.get('name'),'mimeType':mime,'modifiedTime':item.get('modifiedTime'),'createdTime':item.get('createdTime'),'size':item.get('size'),'md5Checksum':item.get('md5Checksum'),'webViewLink':item.get('webViewLink'),'depth':depth+1,'is_folder':is_folder,'is_shortcut':is_shortcut})
                if is_folder: result['folder_count']+=1; q.append((item['id'],p,depth+1))
                if is_shortcut:
                    target=(item.get('shortcutDetails') or {}).get('targetId'); tmime=(item.get('shortcutDetails') or {}).get('targetMimeType')
                    if target and tmime=='application/vnd.google-apps.folder': q.append((target,p+' -> shortcut_target',depth+1))
                if len(result['files'])>=args.max_files: break
        result['file_count']=len(result['files']); result['status']='ok'
    except Exception as e:
        result['status']='error'; result['errors'].append({'error':repr(e)})
    ts=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    write_json(out/'gdrive_recursive_inventory.json',result); write_json(out/f'gdrive_recursive_inventory_{ts}.json',result)
    print(json.dumps({'status':result['status'],'file_count':result['file_count'],'folder_count':result['folder_count'],'errors':len(result['errors'])},indent=2))
if __name__=='__main__': main()
