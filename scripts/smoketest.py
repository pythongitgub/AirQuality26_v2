#!/usr/bin/env python3
"""
AQ26 Secret Smoke Test

Purpose:
- Confirm the current GitHub repository secrets are visible to GitHub Actions.
- Test key external providers without printing any secret values.
- Record provenance, timestamps, provider statuses and redacted diagnostics.
- Avoid failing the whole workflow for optional providers unless core output cannot be written.

This script is intentionally safe:
- It never prints secret values.
- It redacts secret-like URL parameters and headers.
- It writes outputs/01_secrets_smoketest/manifest.json.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


OUTPUT_DIR = Path("outputs/01_secrets_smoketest")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SECRET_GROUPS = {
    "cdse": ["CDSE_ID", "CDSE_SECRET", "CDSE_USERNAME", "CDSE_PASSWORD"],
    "ground_aq": ["WAQI_TOKEN", "OPENWEATHER_KEY", "OPENWEATHER_API_KEY", "OW_KEY"],
    "news": ["NEWS_API_KEY", "NEWSAPI_KEY", "NEWS_DATA_IO_KEY", "NEWSDATA_IO_KEY", "NEWSDATA_KEY"],
    "metoffice": ["MET_OFFICE_API_KEY", "METOFFICE_API_KEY", "MET_OFFICE_KEY", "MET_OFFICE_LAND_OBSERVATIONS"],
    "gdrive": ["GDRIVE_SERVICE_ACCOUNT", "GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS", "GDRIVE_FOLDER_ID"],
    "gemini": ["GEMINI_API_KEY", "GEMINI_MODEL"],
    "email": ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_TO"],
}

SENSITIVE_PARAM_NAMES = {
    "apikey", "api_key", "api-key", "key", "token", "access_token",
    "password", "client_secret", "secret", "authorization", "bearer",
}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_uk(ts: Optional[dt.datetime] = None) -> dt.datetime:
    ts = ts or now_utc()
    if ZoneInfo:
        return ts.astimezone(ZoneInfo("Europe/London"))
    return ts


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def secret_status(name: str) -> Dict[str, Any]:
    value = os.getenv(name, "")
    return {
        "name": name,
        "present": bool(value),
        "length": len(value) if value else 0,
        "sha256_prefix": hashlib.sha256(value.encode("utf-8")).hexdigest()[:10] if value else "",
    }


def get_first_secret(*names: str) -> Tuple[str, str]:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return name, value.strip()
    return "", ""


def redact_text(value: str) -> str:
    if not value:
        return value

    # Redact query parameters.
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.query:
            pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            redacted_pairs = []
            for key, val in pairs:
                if key.lower() in SENSITIVE_PARAM_NAMES or any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                    redacted_pairs.append((key, "***REDACTED***"))
                else:
                    redacted_pairs.append((key, val))
            value = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted_pairs), parsed.fragment)
            )
    except Exception:
        pass

    # Redact common inline forms.
    patterns = [
        r"(?i)(apikey\s*[=:]\s*)[A-Za-z0-9_\-\.]{8,}",
        r"(?i)(api_key\s*[=:]\s*)[A-Za-z0-9_\-\.]{8,}",
        r"(?i)(token\s*[=:]\s*)[A-Za-z0-9_\-\.]{8,}",
        r"(?i)(password\s*[=:]\s*)[^\s&\"']+",
        r"(?i)(client_secret\s*[=:]\s*)[^\s&\"']+",
        r"(?i)(Bearer\s+)[A-Za-z0-9_\-\.]{12,}",
    ]
    for pattern in patterns:
        value = re.sub(pattern, r"\1***REDACTED***", value)
    return value


def safe_url(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return redact_text(url)
    prepared = requests.Request("GET", url, params=params).prepare().url
    return redact_text(prepared or url)


def test_http_json(
    name: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    started = now_utc()
    result = {
        "provider": name,
        "url": safe_url(url, params),
        "started_at_utc": started.isoformat(),
        "started_at_uk": now_uk(started).isoformat(),
        "ok": False,
        "http_status": None,
        "content_type": "",
        "bytes": 0,
        "json_parse_ok": False,
        "record_count_hint": 0,
        "error": "",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        result["http_status"] = response.status_code
        result["content_type"] = response.headers.get("content-type", "")
        result["bytes"] = len(response.content)
        result["ok"] = bool(response.ok)

        try:
            data = response.json()
            result["json_parse_ok"] = True
            result["record_count_hint"] = count_records(data)
            if not response.ok:
                result["error"] = redact_text(json.dumps(data)[:600])
        except Exception:
            result["json_parse_ok"] = False
            if not response.ok:
                result["error"] = redact_text(response.text[:600])

    except Exception as exc:
        result["error"] = redact_text(repr(exc))

    finished = now_utc()
    result["finished_at_utc"] = finished.isoformat()
    result["duration_seconds"] = round((finished - started).total_seconds(), 3)
    return result


def count_records(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ["articles", "results", "features", "value", "items", "data", "list"]:
            val = data.get(key)
            if isinstance(val, list):
                return len(val)
        if isinstance(data.get("result"), dict):
            return count_records(data["result"])
    return 0


def test_waqi() -> Dict[str, Any]:
    token_name, token = get_first_secret("WAQI_TOKEN")
    if not token:
        return skipped("WAQI", "WAQI_TOKEN not present")
    url = "https://api.waqi.info/feed/geo:50.796;0.055/"
    return test_http_json("WAQI Newhaven geospatial feed", url, params={"token": token})


def test_openweather() -> Dict[str, Any]:
    key_name, key = get_first_secret("OPENWEATHER_KEY", "OPENWEATHER_API_KEY", "OW_KEY")
    if not key:
        return skipped("OpenWeather", "OPENWEATHER_KEY / OPENWEATHER_API_KEY / OW_KEY not present")
    url = "https://api.openweathermap.org/data/2.5/weather"
    result = test_http_json(
        f"OpenWeather current weather using {key_name}",
        url,
        params={"lat": 50.796, "lon": 0.055, "appid": key, "units": "metric"},
    )
    result["secret_name_tested"] = key_name
    return result


def test_newsapi() -> Dict[str, Any]:
    key_name, key = get_first_secret("NEWS_API_KEY", "NEWSAPI_KEY")
    if not key:
        return skipped("NewsAPI", "NEWS_API_KEY / NEWSAPI_KEY not present")
    url = "https://newsapi.org/v2/everything"
    result = test_http_json(
        f"NewsAPI using {key_name}",
        url,
        params={"q": "Newhaven incinerator", "language": "en", "pageSize": 1, "apiKey": key},
    )
    result["secret_name_tested"] = key_name
    return result


def test_newsdata() -> Dict[str, Any]:
    key_name, key = get_first_secret("NEWS_DATA_IO_KEY", "NEWSDATA_IO_KEY", "NEWSDATA_KEY")
    if not key:
        return skipped("NewsData.io", "NEWS_DATA_IO_KEY / NEWSDATA_IO_KEY / NEWSDATA_KEY not present")
    url = "https://newsdata.io/api/1/news"
    result = test_http_json(
        f"NewsData.io using {key_name}",
        url,
        params={"apikey": key, "q": "Newhaven incinerator", "language": "en", "size": 1},
    )
    result["secret_name_tested"] = key_name
    return result


def test_metoffice() -> Dict[str, Any]:
    """Try the Met Office Land Observations nearest endpoint with safe key aliases.

    Met Office Weather DataHub uses header:
      apikey: <key>
    """
    key_candidates = [
        ("MET_OFFICE_API_KEY", os.getenv("MET_OFFICE_API_KEY", "").strip()),
        ("METOFFICE_API_KEY", os.getenv("METOFFICE_API_KEY", "").strip()),
        ("MET_OFFICE_KEY", os.getenv("MET_OFFICE_KEY", "").strip()),
    ]
    key_candidates = [(n, v) for n, v in key_candidates if v]
    endpoint = os.getenv("MET_OFFICE_LAND_OBSERVATIONS", "").strip()
    endpoints = []

    # Standard Land Observations nearest endpoint.
    endpoints.append((
        "standard_nearest_land_observations",
        "https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest",
        {"latitude": 50.796, "longitude": 0.055},
    ))

    # Optional configured endpoint, if user stored a full URL.
    if endpoint.startswith("http"):
        endpoints.append(("configured_MET_OFFICE_LAND_OBSERVATIONS", endpoint, {}))

    if not key_candidates:
        return skipped("Met Office", "No MET_OFFICE_API_KEY / METOFFICE_API_KEY / MET_OFFICE_KEY present")

    attempts = []
    for secret_name, key in key_candidates:
        for endpoint_name, url, params in endpoints:
            # Correct documented form.
            headers = {"apikey": key}
            res = test_http_json(
                f"Met Office {endpoint_name} using {secret_name} with apikey header",
                url,
                params=params,
                headers=headers,
            )
            res["secret_name_tested"] = secret_name
            res["endpoint_name_tested"] = endpoint_name
            res["header_style"] = "apikey"
            attempts.append(res)
            if res.get("ok"):
                return {
                    "provider": "Met Office DataHub Land Observations",
                    "ok": True,
                    "selected_secret": secret_name,
                    "selected_endpoint": endpoint_name,
                    "attempts": attempts,
                }

            # Secondary diagnostic only. Some gateways use x-api-key, but Met Office docs say apikey.
            headers = {"x-api-key": key}
            res2 = test_http_json(
                f"Met Office {endpoint_name} using {secret_name} with x-api-key header",
                url,
                params=params,
                headers=headers,
            )
            res2["secret_name_tested"] = secret_name
            res2["endpoint_name_tested"] = endpoint_name
            res2["header_style"] = "x-api-key"
            attempts.append(res2)
            if res2.get("ok"):
                return {
                    "provider": "Met Office DataHub Land Observations",
                    "ok": True,
                    "selected_secret": secret_name,
                    "selected_endpoint": endpoint_name,
                    "attempts": attempts,
                }

    return {
        "provider": "Met Office DataHub Land Observations",
        "ok": False,
        "attempts": attempts,
        "error": "All tested Met Office key/endpoint/header combinations failed. Check subscription product, propagation, key value and endpoint.",
    }


def test_cdse_catalogue() -> Dict[str, Any]:
    """No-auth Copernicus catalogue smoke test.

    CDSE catalogue search is public for metadata. This validates internet/catalogue access
    without printing or using credentials.
    """
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    params = {
        "$filter": "contains(Name,'S5P') and contains(Name,'L2__NO2___')",
        "$top": 1,
        "$orderby": "ContentDate/Start desc",
    }
    return test_http_json("Copernicus Data Space OData catalogue metadata", url, params=params)


def test_gdrive() -> Dict[str, Any]:
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()
    cred_name, cred_text = get_first_secret("GDRIVE_SERVICE_ACCOUNT", "GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS")
    if not folder_id:
        return skipped("Google Drive", "GDRIVE_FOLDER_ID not present")
    if not cred_text:
        return skipped("Google Drive", "GDRIVE_SERVICE_ACCOUNT / GDRIVE_SERVICE_ACCOUNT_JSON / GDRIVE_CREDENTIALS not present")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(cred_text)
        service_email = info.get("client_email", "")
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,mimeType,modifiedTime,size,md5Checksum)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = response.get("files", [])
        return {
            "provider": "Google Drive folder snapshot",
            "ok": True,
            "secret_name_tested": cred_name,
            "service_account_email_present": bool(service_email),
            "folder_id_sha256_prefix": hashlib.sha256(folder_id.encode("utf-8")).hexdigest()[:10],
            "file_count_sample": len(files),
            "sample_names": [f.get("name") for f in files[:5]],
        }
    except Exception as exc:
        return {
            "provider": "Google Drive folder snapshot",
            "ok": False,
            "secret_name_tested": cred_name,
            "folder_id_sha256_prefix": hashlib.sha256(folder_id.encode("utf-8")).hexdigest()[:10],
            "error": redact_text(repr(exc)),
        }


def skipped(provider: str, reason: str) -> Dict[str, Any]:
    return {
        "provider": provider,
        "ok": False,
        "skipped": True,
        "reason": reason,
    }


def write_manifest(manifest: Dict[str, Any]) -> Path:
    path = OUTPUT_DIR / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    started = now_utc()

    secrets = {group: [secret_status(name) for name in names] for group, names in SECRET_GROUPS.items()}
    flat_status = {s["name"]: s for group in secrets.values() for s in group}

    tests = [
        test_waqi(),
        test_openweather(),
        test_newsapi(),
        test_newsdata(),
        test_metoffice(),
        test_cdse_catalogue(),
        test_gdrive(),
    ]

    ok_count = sum(1 for t in tests if t.get("ok"))
    skipped_count = sum(1 for t in tests if t.get("skipped"))
    failed_count = len(tests) - ok_count - skipped_count

    manifest = {
        "step": "01_secrets_smoketest",
        "created_at_utc": started.isoformat(),
        "created_at_uk": now_uk(started).isoformat(),
        "date_uk": now_uk(started).strftime("%d/%m/%Y"),
        "repository": os.getenv("GITHUB_REPOSITORY", ""),
        "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "controlled_use_boundary": (
            "Secret smoke test only. Values are never printed. Provider failures may reflect "
            "propagation delays, subscription/product mismatch, endpoint mismatch or quota/rate limits."
        ),
        "secret_groups": secrets,
        "test_summary": {
            "tests": len(tests),
            "ok": ok_count,
            "failed": failed_count,
            "skipped": skipped_count,
        },
        "provider_tests": tests,
    }

    path = write_manifest(manifest)
    print(json.dumps({
        "manifest": str(path),
        "tests": len(tests),
        "ok": ok_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "metoffice_ok": next((t.get("ok") for t in tests if str(t.get("provider","")).startswith("Met Office")), False),
    }, indent=2))

    # Do not fail the workflow just because an optional provider is temporarily unavailable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
