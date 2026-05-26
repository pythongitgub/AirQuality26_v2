#!/usr/bin/env python3
"""
AQ26 Earthdata authentication smoke test.

Purpose:
- Verify that GitHub Actions can see EARTHDATA_USERNAME, EARTHDATA_PASSWORD and EARTHDATA_TOKEN
  without ever printing their values.
- Verify public CMR collection and granule discovery still works.
- Verify Earthdata Login authentication through the earthaccess Python library when username/password
  are provided.
- Optionally probe the Earthdata Login profile endpoint with EARTHDATA_TOKEN; this is informational
  because token permissions vary by token/application configuration.

This script does not download large NASA datasets.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

CMR = "https://cmr.earthdata.nasa.gov/search"
URS = "https://urs.earthdata.nasa.gov"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding="utf-8")


def secret_state(name: str) -> Dict[str, Any]:
    """Return safe metadata about a secret without exposing the secret."""
    val = os.getenv(name, "") or ""
    return {
        "name": name,
        "present": bool(val),
        "non_empty": bool(val.strip()),
        # Do not expose exact values. Length bucket helps distinguish missing vs obviously truncated.
        "length_bucket": "0" if not val else ("1-20" if len(val) <= 20 else "21-80" if len(val) <= 80 else "81+"),
    }


def sha256_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def safe_http_get(url: str, *, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 60) -> Dict[str, Any]:
    try:
        r = requests.get(url, params=params, headers=headers or {}, timeout=timeout, allow_redirects=True)
        text = r.text or ""
        meta = {
            "ok": bool(r.ok),
            "http_status": int(r.status_code),
            "url": r.url,
            "content_type": r.headers.get("content-type", ""),
            "bytes": len(text.encode("utf-8")),
            "sha256": sha256_text(text[:200000]),
        }
        try:
            payload = r.json()
            return {"meta": meta, "json": payload}
        except Exception:
            return {"meta": meta, "text_preview": text[:500]}
    except Exception as exc:
        return {"meta": {"ok": False, "error": repr(exc), "url": url}}


def count_entries(payload: Dict[str, Any]) -> int:
    js = payload.get("json") or {}
    return len(((js.get("feed") or {}).get("entry") or [])) if isinstance(js, dict) else 0


def test_cmr(timeout: int, user_agent: str) -> Dict[str, Any]:
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    collections = safe_http_get(
        f"{CMR}/collections.json",
        params={"keyword": "air quality", "page_size": 3, "has_granules": "true"},
        headers=headers,
        timeout=timeout,
    )
    collection_entries = count_entries(collections)
    first_collection_id = None
    try:
        entries = collections["json"]["feed"]["entry"]
        if entries:
            first_collection_id = entries[0].get("id")
    except Exception:
        pass

    granules: Dict[str, Any] = {"meta": {"ok": False, "skipped": True, "reason": "no_collection_id"}}
    if first_collection_id:
        granules = safe_http_get(
            f"{CMR}/granules.json",
            params={"collection_concept_id": first_collection_id, "page_size": 2},
            headers=headers,
            timeout=timeout,
        )

    return {
        "status": "ok" if collections.get("meta", {}).get("ok") and collection_entries > 0 else "warning",
        "collection_entries": collection_entries,
        "first_collection_id": first_collection_id,
        "granule_entries": count_entries(granules),
        "collections_http": collections.get("meta", {}),
        "granules_http": granules.get("meta", {}),
    }


def test_earthaccess_login() -> Dict[str, Any]:
    username_present = bool(os.getenv("EARTHDATA_USERNAME"))
    password_present = bool(os.getenv("EARTHDATA_PASSWORD"))
    if not (username_present and password_present):
        return {"status": "skipped", "reason": "EARTHDATA_USERNAME and/or EARTHDATA_PASSWORD missing"}

    try:
        import earthaccess  # type: ignore
    except Exception as exc:
        return {"status": "failed", "reason": "earthaccess import failed", "error": repr(exc)}

    try:
        # earthaccess reads EARTHDATA_USERNAME / EARTHDATA_PASSWORD from the environment.
        auth = earthaccess.login(strategy="environment", persist=False)
        # Avoid printing auth internals; they can contain credential/session details.
        return {"status": "ok", "auth_object_type": type(auth).__name__}
    except Exception as exc:
        return {"status": "failed", "reason": "earthaccess environment login failed", "error": repr(exc)}


def test_bearer_token_profile(timeout: int) -> Dict[str, Any]:
    token = os.getenv("EARTHDATA_TOKEN", "") or ""
    username = os.getenv("EARTHDATA_USERNAME", "") or ""
    if not token:
        return {"status": "skipped", "reason": "EARTHDATA_TOKEN missing"}
    if not username:
        return {"status": "skipped", "reason": "EARTHDATA_USERNAME missing; cannot safely build profile URL"}

    # This is intentionally informational: Earthdata token/API permissions vary.
    url = f"{URS}/api/users/{username}"
    res = safe_http_get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=timeout)
    meta = res.get("meta", {})
    return {
        "status": "ok" if meta.get("ok") else "warning",
        "http_status": meta.get("http_status"),
        "content_type": meta.get("content_type"),
        "bytes": meta.get("bytes"),
        "note": "Bearer-token profile probe is informational; username/password earthaccess login is the primary GitHub credential test.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out-dir", default="outputs/34_earthdata_auth")
    ap.add_argument("--site-dir", default="site_public/data/providers/earthdata")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--fail-on-auth-warning", action="store_true")
    ap.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26 Earthdata auth smoke test"))
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    out_dir = repo / args.out_dir
    site_dir = repo / args.site_dir
    mkdir(out_dir)
    mkdir(site_dir)

    secrets = [secret_state(n) for n in ["EARTHDATA_USERNAME", "EARTHDATA_PASSWORD", "EARTHDATA_TOKEN"]]
    cmr = test_cmr(args.timeout, args.user_agent)
    earthaccess_login = test_earthaccess_login()
    token_profile = test_bearer_token_profile(args.timeout)

    credentials_present = all(x["present"] and x["non_empty"] for x in secrets[:2])
    token_present = secrets[2]["present"] and secrets[2]["non_empty"]
    cmr_ok = cmr.get("status") == "ok"
    earthaccess_ok = earthaccess_login.get("status") == "ok"

    # Token profile warnings do not necessarily mean the token is unusable for data workflows.
    status = "ok" if credentials_present and token_present and cmr_ok and earthaccess_ok else "warning"
    hard_fail = False
    if not credentials_present or not token_present:
        hard_fail = bool(args.fail_on_auth_warning)
    if not cmr_ok or not earthaccess_ok:
        hard_fail = bool(args.fail_on_auth_warning)

    summary = {
        "provider": "nasa_earthdata_auth_smoke_test",
        "status": "failed" if hard_fail else status,
        "generated_utc": utc_now(),
        "secrets_safe_state": secrets,
        "cmr_public_discovery_test": cmr,
        "earthaccess_environment_login_test": earthaccess_login,
        "earthdata_token_profile_probe": token_profile,
        "interpretation": {
            "ready_for_cmr_discovery": bool(cmr_ok),
            "ready_for_authenticated_earthaccess_workflows": bool(earthaccess_ok),
            "ready_for_large_downloads": False,
            "next_step": "Run CMR discovery first; only test tiny selected OPeNDAP/download subsets after a product is chosen.",
        },
    }

    source_records = [
        {
            "source_type": "nasa_earthdata_login",
            "source_class": "credential_smoke_test",
            "provider": "NASA Earthdata Login / earthaccess",
            "title": "Earthdata GitHub Actions credential smoke test",
            "status": earthaccess_login.get("status"),
            "retrieved_at_utc": utc_now(),
            "record_count": 1 if earthaccess_ok else 0,
            "provenance_level": "credential_runtime_check_no_secret_values_written",
            "notes": "No secret values are printed or persisted. This confirms whether GitHub Actions can authenticate via environment secrets.",
        },
        {
            "source_type": "nasa_earthdata_cmr",
            "source_class": "public_catalogue_smoke_test",
            "provider": "NASA Common Metadata Repository",
            "title": "CMR public collection and granule smoke test",
            "status": cmr.get("status"),
            "retrieved_at_utc": utc_now(),
            "record_count": int(cmr.get("collection_entries") or 0),
            "provenance_level": "official_machine_readable_catalogue",
            "notes": "CMR catalogue discovery does not require Earthdata Login, but it verifies network/API behaviour from GitHub Actions.",
        },
    ]

    write_json(out_dir / "earthdata_auth_smoke_summary.json", summary)
    write_json(out_dir / "earthdata_auth_source_records.json", source_records)
    write_json(site_dir / "auth_smoke_summary.json", summary)
    write_json(site_dir / "auth_smoke_source_records.json", source_records)

    print(json.dumps({
        "status": summary["status"],
        "cmr_status": cmr.get("status"),
        "earthaccess_login_status": earthaccess_login.get("status"),
        "token_profile_status": token_profile.get("status"),
        "ready_for_authenticated_earthaccess_workflows": earthaccess_ok,
    }, indent=2))

    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
