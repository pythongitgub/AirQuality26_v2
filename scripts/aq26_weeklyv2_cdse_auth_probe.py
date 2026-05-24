#!/usr/bin/env python3
"""
AQ26 WeeklyV2 CDSE dual-auth probe.

Tests both Copernicus Data Space authentication routes safely:

1. OData product-download route:
   grant_type=password
   username=CDSE_USERNAME
   password=CDSE_PASSWORD
   client_id=cdse-public

2. Sentinel Hub OAuth route:
   grant_type=client_credentials
   client_id=CDSE_ID
   client_secret=CDSE_SECRET

No access tokens, refresh tokens, passwords or client secrets are written to disk or logs.
Only readiness booleans, status codes and redacted error summaries are stored.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict

import requests

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


def env(name: str) -> str:
    return os.getenv(name, "").strip()


def redacted_error_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'(?i)("access_token"\s*:\s*")[^"]+(")', r'\1***REDACTED***\2', text)
    text = re.sub(r'(?i)("refresh_token"\s*:\s*")[^"]+(")', r'\1***REDACTED***\2', text)
    text = re.sub(r'(?i)("password"\s*:\s*")[^"]+(")', r'\1***REDACTED***\2', text)
    text = re.sub(r'(?i)("client_secret"\s*:\s*")[^"]+(")', r'\1***REDACTED***\2', text)
    text = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_\-.]+', r'\1***REDACTED***', text)
    return text[:800]


def token_response_summary(response: requests.Response) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "http_status": response.status_code,
        "ok": response.ok,
        "content_type": response.headers.get("content-type", ""),
        "token_ready": False,
        "expires_in": None,
        "token_type_present": False,
        "error": "",
        "error_description": "",
    }
    try:
        data = response.json()
    except Exception:
        out["error"] = redacted_error_text(response.text)
        return out

    out["token_ready"] = bool(response.ok and data.get("access_token"))
    out["expires_in"] = data.get("expires_in")
    out["token_type_present"] = bool(data.get("token_type"))
    if not response.ok:
        out["error"] = redacted_error_text(str(data.get("error", "")))
        out["error_description"] = redacted_error_text(str(data.get("error_description", "")))
    return out


def post_token(data: Dict[str, str]) -> Dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=40,
    )
    return token_response_summary(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    out_dir = output_root / "15_optional_sources"
    out_dir.mkdir(parents=True, exist_ok=True)

    cdse_username = env("CDSE_USERNAME")
    cdse_password = env("CDSE_PASSWORD")
    cdse_id = env("CDSE_ID")
    cdse_secret = env("CDSE_SECRET")

    created = dt.datetime.now(dt.timezone.utc).isoformat()

    result: Dict[str, Any] = {
        "created_at_utc": created,
        "provider": "Copernicus Data Space Ecosystem",
        "token_endpoint": TOKEN_URL,
        "secrets_present": {
            "CDSE_USERNAME": bool(cdse_username),
            "CDSE_PASSWORD": bool(cdse_password),
            "CDSE_ID": bool(cdse_id),
            "CDSE_SECRET": bool(cdse_secret),
        },
        "credential_fingerprints": {
            # Prefix hashes help confirm the same secret was tested without exposing it.
            "CDSE_USERNAME_sha256_prefix": hashlib.sha256(cdse_username.encode()).hexdigest()[:10] if cdse_username else "",
            "CDSE_ID_sha256_prefix": hashlib.sha256(cdse_id.encode()).hexdigest()[:10] if cdse_id else "",
        },
        "odata_password_grant": {
            "auth_mode": "password",
            "client_id_used": "cdse-public",
            "credentials_used": ["CDSE_USERNAME", "CDSE_PASSWORD"],
            "attempted": False,
            "token_ready": False,
            "download_auth_ready": False,
            "notes": "Used for OData product download route; no token is stored.",
        },
        "sentinelhub_client_credentials": {
            "auth_mode": "client_credentials",
            "credentials_used": ["CDSE_ID", "CDSE_SECRET"],
            "attempted": False,
            "token_ready": False,
            "sentinelhub_auth_ready": False,
            "notes": "Used for Sentinel Hub APIs if OAuth client credentials are valid; no token is stored.",
        },
        "cdse_catalogue_ready": True,
        "cdse_download_ready": False,
        "cdse_auth_ready": False,
        "recommendation": "",
    }

    if cdse_username and cdse_password:
        result["odata_password_grant"]["attempted"] = True
        try:
            summary = post_token({
                "grant_type": "password",
                "username": cdse_username,
                "password": cdse_password,
                "client_id": "cdse-public",
            })
            result["odata_password_grant"].update(summary)
            result["odata_password_grant"]["download_auth_ready"] = bool(summary.get("token_ready"))
        except Exception as exc:
            result["odata_password_grant"].update({
                "http_status": None,
                "ok": False,
                "token_ready": False,
                "error": redacted_error_text(repr(exc)),
            })
    else:
        result["odata_password_grant"]["notes"] += " Missing CDSE_USERNAME or CDSE_PASSWORD."

    if cdse_id and cdse_secret:
        result["sentinelhub_client_credentials"]["attempted"] = True
        try:
            summary = post_token({
                "grant_type": "client_credentials",
                "client_id": cdse_id,
                "client_secret": cdse_secret,
            })
            result["sentinelhub_client_credentials"].update(summary)
            result["sentinelhub_client_credentials"]["sentinelhub_auth_ready"] = bool(summary.get("token_ready"))
        except Exception as exc:
            result["sentinelhub_client_credentials"].update({
                "http_status": None,
                "ok": False,
                "token_ready": False,
                "error": redacted_error_text(repr(exc)),
            })
    else:
        result["sentinelhub_client_credentials"]["notes"] += " Missing CDSE_ID or CDSE_SECRET."

    result["cdse_download_ready"] = bool(result["odata_password_grant"].get("download_auth_ready"))
    result["cdse_sentinelhub_ready"] = bool(result["sentinelhub_client_credentials"].get("sentinelhub_auth_ready"))
    result["cdse_auth_ready"] = bool(result["cdse_download_ready"] or result["cdse_sentinelhub_ready"])

    if result["cdse_download_ready"] and not result["cdse_sentinelhub_ready"]:
        result["recommendation"] = "OData username/password route works. Keep CDSE_ID/CDSE_SECRET separate for Sentinel Hub or ignore until Sentinel Hub APIs are needed."
    elif result["cdse_sentinelhub_ready"] and not result["cdse_download_ready"]:
        result["recommendation"] = "Sentinel Hub OAuth route works. OData download username/password route still needs attention."
    elif result["cdse_download_ready"] and result["cdse_sentinelhub_ready"]:
        result["recommendation"] = "Both CDSE auth routes are ready."
    else:
        result["recommendation"] = "Neither CDSE auth route returned a token. Check username/password for OData and client id/secret for Sentinel Hub."

    out = out_dir / "cdse_auth_readiness.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "cdse_download_ready": result["cdse_download_ready"],
        "cdse_sentinelhub_ready": result["cdse_sentinelhub_ready"],
        "cdse_auth_ready": result["cdse_auth_ready"],
        "output": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
