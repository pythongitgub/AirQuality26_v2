#!/usr/bin/env python3
"""
AQ26 integrated evidence harvest.

Hardening in this version:
- Met Office Land Observations nearest endpoint uses `lat` / `lon` and rounds to max 2 decimals.
- GDELT requests use 7 second spacing plus one retry after 429.
- Source URLs are redacted before being written.
- Google Drive snapshot remains metadata-only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

SOURCE_RECORDS: List[Dict[str, Any]] = []
RUN_TS = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LAST_GDELT_CALL = 0.0


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def uk_time(t: dt.datetime | None = None) -> dt.datetime:
    t = t or now_utc()
    return t.astimezone(ZoneInfo("Europe/London")) if ZoneInfo else t


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")[:100] or "item"


def env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value.strip()
    return ""


def redact(value: str) -> str:
    if not value:
        return value
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.query:
            pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            redacted = []
            for key, val in pairs:
                if any(x in key.lower() for x in ["key", "apikey", "token", "secret", "password"]):
                    redacted.append((key, "***REDACTED***"))
                else:
                    redacted.append((key, val))
            value = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
            )
    except Exception:
        pass
    value = re.sub(
        r"(?i)(apikey|api_key|token|password|client_secret)=([^&\s]+)",
        r"\1=***REDACTED***",
        value,
    )
    return value


def safe_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: safe_json(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [safe_json(x) for x in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj


def write_json(path: Path, obj: Any) -> Path:
    mkdir(path.parent)
    path.write_text(json.dumps(safe_json(obj), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_bytes(path: Path, content: bytes) -> Path:
    mkdir(path.parent)
    path.write_bytes(content)
    return path


def full_url(url: str, params: Dict[str, Any] | None) -> str:
    if not params:
        return url
    return requests.Request("GET", url, params=params).prepare().url or url


def count_records(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ["articles", "results", "features", "value", "items", "data", "list"]:
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
        if isinstance(data.get("result"), dict):
            return count_records(data["result"])
    return 0


def request_get(url: str, params: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None, timeout: int = 30):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        try:
            data = response.json()
        except Exception:
            data = None
        error = "" if response.ok else (json.dumps(data)[:700] if data is not None else response.text[:700])
        return data, response.status_code, response.content, error
    except Exception as exc:
        return None, None, json.dumps({"error": repr(exc)}).encode("utf-8"), repr(exc)


def add_record(name: str, typ: str, url: str, query: str, status: str, http_status, path: Path | None,
               record_count: int, error: str = "", notes: str = "") -> Dict[str, Any]:
    t = now_utc()
    u = uk_time(t)
    item = {
        "run_ts": RUN_TS,
        "source_name": name,
        "source_type": typ,
        "url": redact(url),
        "query": query,
        "status": status,
        "http_status": http_status,
        "retrieved_at_utc": t.isoformat(),
        "retrieved_at_uk": u.isoformat(),
        "date_uk": u.strftime("%d/%m/%Y"),
        "output_path": str(path).replace("\\", "/") if path else "",
        "sha256": sha_file(path) if path and path.exists() else "",
        "bytes": path.stat().st_size if path and path.exists() else 0,
        "record_count": int(record_count or 0),
        "error": redact(error or ""),
        "notes": notes,
    }
    SOURCE_RECORDS.append(item)
    return item


def date_window(lookback_days: int, start_date: str, end_date: str) -> tuple[str, str]:
    if start_date:
        start = dt.date.fromisoformat(start_date)
        end = dt.date.fromisoformat(end_date) if end_date else now_utc().date()
    else:
        end = now_utc().date()
        start = end - dt.timedelta(days=int(lookback_days))
    return start.isoformat(), end.isoformat()


def gdelt_get(url: str, params: Dict[str, Any]):
    global LAST_GDELT_CALL
    elapsed = time.time() - LAST_GDELT_CALL
    if elapsed < 7.0:
        time.sleep(7.0 - elapsed)
    data, status, content, error = request_get(url, params=params)
    LAST_GDELT_CALL = time.time()
    if status == 429:
        time.sleep(10.0)
        data, status, content, error = request_get(url, params=params)
        LAST_GDELT_CALL = time.time()
    return data, status, content, error


def harvest_news(cfg: Dict[str, Any], output_root: Path, start_date: str) -> None:
    raw_dir = mkdir(output_root / "03_news_context" / "raw")
    articles = []
    newsapi = env_first("NEWS_API_KEY", "NEWSAPI_KEY")
    newsdata = env_first("NEWS_DATA_IO_KEY", "NEWSDATA_IO_KEY", "NEWSDATA_KEY")

    for query in cfg.get("news_queries", []):
        if newsapi:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 50,
                "from": start_date,
                "apiKey": newsapi,
            }
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(raw_dir / f"newsapi_{slug(query)}_{RUN_TS}.json", content)
            add_record("NewsAPI everything", "news_api", full_url(url, params), query,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)
            if isinstance(data, dict) and isinstance(data.get("articles"), list):
                for item in data["articles"]:
                    item["_aq26_provider"] = "NewsAPI"
                    item["_aq26_query"] = query
                    articles.append(item)

        if newsdata:
            url = "https://newsdata.io/api/1/news"
            params = {"apikey": newsdata, "q": query, "language": "en", "size": 10}
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(raw_dir / f"newsdata_{slug(query)}_{RUN_TS}.json", content)
            add_record("NewsData.io news", "news_api", full_url(url, params), query,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                for item in data["results"]:
                    item["_aq26_provider"] = "NewsData.io"
                    item["_aq26_query"] = query
                    articles.append(item)

        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": 50, "sort": "HybridRel"}
        data, status, content, error = gdelt_get(url, params)
        path = write_bytes(raw_dir / f"gdelt_{slug(query)}_{RUN_TS}.json", content)
        add_record("GDELT document API", "news_api", full_url(url, params), query,
                   "ok" if status and status < 400 else "error", status, path, count_records(data), error)

    write_json(output_root / "03_news_context" / "news_articles.json",
               {"run_ts": RUN_TS, "count": len(articles), "articles": articles})


def metoffice_coord(value: float) -> str:
    # Met Office DataHub nearest endpoint requires at most two decimal places.
    return f"{float(value):.2f}"


def harvest_aq_weather(cfg: Dict[str, Any], output_root: Path) -> None:
    raw_dir = mkdir(output_root / "04_ground_aq_providers" / "raw")
    waqi = env_first("WAQI_TOKEN")
    openweather = env_first("OPENWEATHER_KEY", "OPENWEATHER_API_KEY", "OW_KEY")

    for site in cfg.get("sites", []):
        site_id = site["id"]
        lat = site["lat"]
        lon = site["lon"]

        if waqi:
            url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
            params = {"token": waqi}
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(raw_dir / f"waqi_{site_id}_{RUN_TS}.json", content)
            add_record("WAQI geospatial feed", "ground_aq", full_url(url, params), site_id,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)

        if openweather:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {"lat": lat, "lon": lon, "appid": openweather, "units": "metric"}
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(output_root / "05_weather" / "raw" / f"openweather_current_{site_id}_{RUN_TS}.json", content)
            add_record("OpenWeather current weather", "weather", full_url(url, params), site_id,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)

            url = "https://api.openweathermap.org/data/2.5/air_pollution"
            params = {"lat": lat, "lon": lon, "appid": openweather}
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(raw_dir / f"openweather_airpollution_{site_id}_{RUN_TS}.json", content)
            add_record("OpenWeather air pollution", "ground_aq", full_url(url, params), site_id,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)

    met_key = env_first("MET_OFFICE_API_KEY", "METOFFICE_API_KEY", "MET_OFFICE_KEY")
    if met_key:
        focus_site = cfg.get("sites", [{"lat": 50.796, "lon": 0.055}])[0]
        url = "https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest"
        params = {"lat": metoffice_coord(focus_site.get("lat", 50.796)), "lon": metoffice_coord(focus_site.get("lon", 0.055))}
        data, status, content, error = request_get(url, params=params, headers={"apikey": met_key})
        path = write_bytes(output_root / "05_metoffice_datahub_weather" / f"metoffice_land_observations_{RUN_TS}.json", content)
        add_record("Met Office DataHub land observations", "weather", full_url(url, params), "newhaven_nearest",
                   "ok" if status and status < 400 else "error", status, path, count_records(data), error,
                   notes="uses apikey header and lat/lon parameters rounded to 2 decimals")


def harvest_official(cfg: Dict[str, Any], output_root: Path) -> None:
    filings = []
    raw_dir = mkdir(output_root / "06_official_filings" / "raw")
    relevance_terms = [
        term.lower()
        for term in cfg.get("thresholds", {}).get("anomaly", {}).get("official_relevance_terms", [])
    ]

    for query in cfg.get("official_queries", []):
        targets = [
            ("GOV.UK", "https://www.gov.uk/api/search.json", {"q": query, "count": 50}),
            ("data.gov.uk", "https://ckan.publishing.service.gov.uk/api/3/action/package_search", {"q": query, "rows": 50}),
        ]
        for source, url, params in targets:
            data, status, content, error = request_get(url, params=params)
            path = write_bytes(raw_dir / f"{slug(source)}_{slug(query)}_{RUN_TS}.json", content)
            add_record(f"{source} search", "official_search", full_url(url, params), query,
                       "ok" if status and status < 400 else "error", status, path, count_records(data), error)

            if source == "GOV.UK" and isinstance(data, dict):
                for row in data.get("results", []):
                    filings.append({
                        "source": source,
                        "query": query,
                        "title": row.get("title"),
                        "url": urllib.parse.urljoin("https://www.gov.uk", row.get("link", "")),
                        "raw": row,
                    })

            if source == "data.gov.uk" and isinstance(data, dict) and isinstance(data.get("result"), dict):
                for row in data["result"].get("results", []):
                    filings.append({
                        "source": source,
                        "query": query,
                        "title": row.get("title"),
                        "url": row.get("url") or "",
                        "raw": row,
                    })

    for item in cfg.get("watch_urls", []):
        data, status, content, error = request_get(item["url"])
        path = write_bytes(raw_dir / f"watch_{slug(item.get('name', 'watch'))}_{RUN_TS}.html", content)
        add_record(item.get("name", "Watch URL"), "official_watch_url", item["url"], item.get("name", ""),
                   "ok" if status and status < 400 else "error", status, path, 1 if status and status < 400 else 0, error)
        filings.append({"source": "watch_url", "query": item.get("name"), "title": item.get("name"), "url": item["url"], "raw_path": str(path)})

    for item in filings:
        text = json.dumps(item, ensure_ascii=False).lower()
        hits = [term for term in relevance_terms if term in text]
        item["aq26_relevance_hits"] = hits
        item["aq26_relevance_class"] = "confirmed_or_probable" if len(hits) >= 2 else ("candidate_context" if hits else "weak_or_irrelevant")

    write_json(output_root / "06_official_filings" / "official_filing_index.json",
               {"run_ts": RUN_TS, "filing_count": len(filings), "filings": filings})
    change_items = []
    for item in filings:
        fingerprint = hashlib.sha256(json.dumps(safe_json(item), sort_keys=True, default=str).encode("utf-8")).hexdigest()
        change_items.append({
            "change_status": "seen_this_run",
            "fingerprint": fingerprint,
            "title": item.get("title"),
            "url": item.get("url"),
            "source": item.get("source"),
            "query": item.get("query"),
            "relevance_class": item.get("aq26_relevance_class"),
        })
    write_json(output_root / "06_official_filings" / "new_or_changed_source_index.json",
               {"run_ts": RUN_TS, "items": change_items})


def harvest_satellite(cfg: Dict[str, Any], output_root: Path, start_date: str, end_date: str) -> None:
    raw_dir = mkdir(output_root / "07_satellite_cdse" / "raw")
    sat_cfg = cfg.get("satellite", {})
    bbox = sat_cfg.get("bbox", [-0.15, 50.68, 0.35, 50.95])
    metadata = {"run_ts": RUN_TS, "bbox": bbox, "start_date": start_date, "end_date": end_date, "odata": [], "product_count": 0}

    base_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    products = sat_cfg.get("collections", {}).get(
        "odata_products",
        ["L2__NO2___", "L2__SO2___", "L2__CO____", "L2__HCHO__", "L2__O3____", "L2__CH4___", "L2__AER_AI"],
    )
    max_records = int(sat_cfg.get("max_records_per_product", 50))

    for product in products:
        filter_text = (
            f"contains(Name,'S5P') and contains(Name,'{product}') "
            f"and ContentDate/Start ge {start_date}T00:00:00.000Z "
            f"and ContentDate/Start le {end_date}T23:59:59.000Z"
        )
        params = {"$filter": filter_text, "$top": max_records, "$orderby": "ContentDate/Start desc"}
        data, status, content, error = request_get(base_url, params=params)
        path = write_bytes(raw_dir / f"copernicus_odata_{product}_{RUN_TS}.json", content)
        found = count_records(data)
        metadata["odata"].append({"product": product, "http_status": status, "count": found, "path": str(path), "bbox_context": bbox})
        metadata["product_count"] += found
        add_record("Copernicus Data Space OData product search", "satellite_metadata", full_url(base_url, params), product,
                   "ok" if status and status < 400 else "error", status, path, found, error,
                   notes=f"bbox context={bbox}; catalogue only, not pollutant extraction")

    write_json(output_root / "07_satellite_cdse" / "satellite_catalogue_metadata.json", metadata)


def harvest_gdrive(output_root: Path, folder_id: str) -> None:
    if os.getenv("AQ26_SYNC_GOOGLE_DRIVE", "").lower() not in ("1", "true", "yes", "y"):
        add_record("Google Drive folder snapshot", "gdrive", "gdrive://disabled", "", "skipped", None, None, 0, notes="sync disabled")
        return

    folder_id = folder_id or os.getenv("GDRIVE_FOLDER_ID", "")
    cred_text = env_first("GDRIVE_SERVICE_ACCOUNT", "GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS")
    if not folder_id or not cred_text:
        add_record("Google Drive folder snapshot", "gdrive", f"gdrive://{folder_id or 'missing'}", "", "skipped", None, None, 0,
                   notes="missing folder id or service account")
        return

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(cred_text)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        files = []
        page_token = None
        for _ in range(20):
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,modifiedTime,size,md5Checksum,webViewLink,parents)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        path = write_json(output_root / "08_gdrive_snapshot" / f"gdrive_folder_snapshot_{RUN_TS}.json",
                          {"run_ts": RUN_TS, "folder_id": folder_id, "file_count": len(files), "files": files})
        add_record("Google Drive folder snapshot", "gdrive", f"gdrive://{folder_id}", folder_id, "ok", None, path, len(files),
                   notes="metadata only")
    except Exception as exc:
        path = write_json(output_root / "08_gdrive_snapshot" / f"gdrive_error_{RUN_TS}.json", {"error": repr(exc)})
        add_record("Google Drive folder snapshot", "gdrive", f"gdrive://{folder_id}", folder_id, "error", None, path, 0, repr(exc))


def finish(output_root: Path, cfg: Dict[str, Any], start_date: str, end_date: str) -> None:
    mkdir(output_root / "source_history")
    with (output_root / "source_history" / "source_index.jsonl").open("a", encoding="utf-8") as handle:
        for row in SOURCE_RECORDS:
            handle.write(json.dumps(safe_json(row), ensure_ascii=False) + "\n")

    latest = {
        "run_ts": RUN_TS,
        "project": cfg.get("project", {}).get("name", "SCCNEXUS AirQuality26"),
        "controlled_use_boundary": cfg.get("project", {}).get("controlled_use_boundary", ""),
        "date_window": {"start": start_date, "end": end_date},
        "source_record_count": len(SOURCE_RECORDS),
        "ok_count": sum(1 for row in SOURCE_RECORDS if row["status"] == "ok"),
        "error_count": sum(1 for row in SOURCE_RECORDS if row["status"] == "error"),
        "source_records": SOURCE_RECORDS,
    }
    write_json(output_root / "00_live_harvest" / "LATEST_HARVEST.json", latest)
    run_dir = mkdir(output_root / "00_live_harvest" / f"AQ26_LIVE_HARVEST_{RUN_TS}")
    write_json(run_dir / f"AQ26_LIVE_HARVEST_MANIFEST_{RUN_TS}.json", latest)

    if SOURCE_RECORDS:
        with (run_dir / f"AQ26_LIVE_SOURCE_RECORDS_{RUN_TS}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(SOURCE_RECORDS[0].keys()))
            writer.writeheader()
            writer.writerows(SOURCE_RECORDS)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_integrated_sources.yml")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--lookback-days", default="14")
    parser.add_argument("--backfill-start-date", default="")
    parser.add_argument("--backfill-end-date", default="")
    parser.add_argument("--download-official-files", default="false")
    parser.add_argument("--sync-google-drive", default="false")
    parser.add_argument("--gdrive-folder-id", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    mkdir(output_root)
    os.environ["AQ26_SYNC_GOOGLE_DRIVE"] = args.sync_google_drive

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    start_date, end_date = date_window(int(args.lookback_days), args.backfill_start_date.strip(), args.backfill_end_date.strip())

    harvest_news(cfg, output_root, start_date)
    harvest_aq_weather(cfg, output_root)
    harvest_official(cfg, output_root)
    harvest_satellite(cfg, output_root, start_date, end_date)
    harvest_gdrive(output_root, args.gdrive_folder_id.strip())
    finish(output_root, cfg, start_date, end_date)

    print(json.dumps({
        "run_ts": RUN_TS,
        "source_records": len(SOURCE_RECORDS),
        "ok": sum(1 for row in SOURCE_RECORDS if row["status"] == "ok"),
        "error": sum(1 for row in SOURCE_RECORDS if row["status"] == "error"),
    }, indent=2))


if __name__ == "__main__":
    main()
