#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, datetime as dt
from pathlib import Path
from typing import Any, Dict, List

UTC = dt.timezone.utc

def now_utc() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")

def mkdir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True); return p

def sha256_file(path: Path, chunk_size: int = 1024*1024) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(chunk_size), b""):
            h.update(b)
    return h.hexdigest()

def sha256_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def redact_str(s: str) -> str:
    if not isinstance(s, str): return s
    s = re.sub(r"(?i)(apikey|api_key|token|password|secret|client_secret|key)=([^&\s]+)", r"\1=***REDACTED***", s)
    s = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{12,}", r"\1***REDACTED***", s)
    return s

def safe_json(x: Any) -> Any:
    if isinstance(x, dict): return {k: safe_json(v) for k,v in x.items()}
    if isinstance(x, list): return [safe_json(v) for v in x]
    if isinstance(x, str): return redact_str(x)
    return x

def write_json(path: Path, obj: Any) -> Path:
    path=Path(path); mkdir(path.parent)
    path.write_text(json.dumps(safe_json(obj), indent=2, ensure_ascii=False, default=str, sort_keys=True), encoding="utf-8")
    return path

def read_json(path: Path, default=None) -> Any:
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return default

def write_csv(path: Path, rows: List[Dict[str, Any]]) -> Path:
    import pandas as pd
    path=Path(path); mkdir(path.parent)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path

def relpath(path: Path, root: Path) -> str:
    try: return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\","/")
    except Exception: return str(path)

def file_manifest(root: Path, label: str = "") -> List[Dict[str, Any]]:
    root=Path(root)
    out=[]
    if not root.exists(): return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st=p.stat()
            out.append({"label":label, "path":str(p), "relative_path":str(p.relative_to(root)).replace("\\","/"),
                        "size_bytes":st.st_size, "sha256":sha256_file(p), "modified_utc":dt.datetime.fromtimestamp(st.st_mtime, UTC).isoformat()})
    return out

def source_record(title: str, provider: str, status: str, record_count: int = 0, output_path: str = "", notes: str = "", **kw) -> Dict[str, Any]:
    return {"title":title, "provider":provider, "status":status, "record_count":int(record_count or 0),
            "retrieved_at_utc":now_utc(), "output_path":output_path, "notes":notes, **kw}
