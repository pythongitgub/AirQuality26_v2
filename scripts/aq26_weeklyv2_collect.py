#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, datetime as dt, hashlib, json, os, re, time, urllib.parse
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

RUN_TS = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RECORDS: List[Dict[str, Any]] = []
WARNINGS: List[Dict[str, Any]] = []
OPENAQ_SAFETY = {
    "run_ts": RUN_TS,
    "enabled": False,
    "request_count": 0,
    "max_requests_per_run": 0,
    "min_seconds_between_requests": 0,
    "stopped_reason": "",
    "rate_limit_seen": False,
    "auth_error_seen": False,
    "status_codes": [],
    "site_ids": [],
    "notes": "OpenAQ is intentionally low-rate: no pagination storm, no repeated retries, stop on 401/403/429.",
}
LAST_OPENAQ = 0.0
LAST_CAMS = 0.0
LAST_GDELT = 0.0


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def uk_time(t=None):
    t = t or now_utc()
    return t.astimezone(ZoneInfo("Europe/London")) if ZoneInfo else t


def mkdir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def env_first(*names):
    for n in names:
        v = os.getenv(n, "")
        if v:
            return v.strip()
    return ""


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "")
    if v == "":
        return bool(default)
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_backfill_mode() -> bool:
    return env_bool("AQ26_BACKFILL_MODE", False) or bool(os.getenv("AQ26_HISTORY_START_DATE") or os.getenv("AQ26_WINDOW_START_DATE"))


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s)).strip("_")[:120] or "item"


def redact(s: str) -> str:
    if not s:
        return s
    try:
        u = urllib.parse.urlsplit(s)
        if u.query:
            pairs = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
            red = []
            for k, v in pairs:
                red.append((k, "***REDACTED***" if any(x in k.lower() for x in ["key", "apikey", "token", "secret", "password"]) else v))
            s = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(red), u.fragment))
    except Exception:
        pass
    s = re.sub(r"(?i)(apikey|api_key|token|password|client_secret)=([^&\s]+)", r"\1=***REDACTED***", s)
    s = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{12,}", r"\1***REDACTED***", s)
    return s


def safe_json(x):
    if isinstance(x, dict):
        return {k: safe_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [safe_json(v) for v in x]
    if isinstance(x, str):
        return redact(x)
    return x


def write_json(path: Path, obj: Any) -> Path:
    mkdir(path.parent)
    path.write_text(json.dumps(safe_json(obj), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_bytes(path: Path, content: bytes) -> Path:
    mkdir(path.parent)
    path.write_bytes(content)
    return path


def full_url(url, params=None):
    return requests.Request("GET", url, params=params).prepare().url if params else url


def count_records(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for k in ["articles", "results", "features", "value", "items", "data", "list"]:
            if isinstance(data.get(k), list):
                return len(data[k])
        if isinstance(data.get("result"), dict):
            return count_records(data["result"])
    return 0


def add_warning(provider: str, query: str, http_status=None, error: str = "", notes: str = ""):
    t = now_utc()
    WARNINGS.append({
        "run_ts": RUN_TS,
        "provider": provider,
        "query": query,
        "http_status": http_status,
        "warning_at_utc": t.isoformat(),
        "warning_at_uk": uk_time(t).isoformat(),
        "error": redact(error or ""),
        "notes": notes,
    })


def add_record(name, typ, url, query, status, http_status, path=None, record_count=0, error="", notes=""):
    t = now_utc()
    u = uk_time(t)
    row = {
        "run_ts": RUN_TS,
        "source_name": name,
        "source_type": typ,
        "url": redact(url or ""),
        "query": query or "",
        "status": status,
        "http_status": http_status,
        "retrieved_at_utc": t.isoformat(),
        "retrieved_at_uk": u.isoformat(),
        "date_uk": u.strftime("%d/%m/%Y"),
        "output_path": str(path).replace("\\", "/") if path else "",
        "sha256": sha_file(path) if path and Path(path).exists() else "",
        "bytes": Path(path).stat().st_size if path and Path(path).exists() else 0,
        "record_count": int(record_count or 0),
        "error": redact(error or ""),
        "notes": notes or "",
    }
    RECORDS.append(row)
    return row


def request_get(url, params=None, headers=None, timeout=30):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = None
        error = "" if r.ok else (json.dumps(data)[:700] if data is not None else r.text[:700])
        return data, r.status_code, r.content, error, dict(r.headers)
    except Exception as e:
        return None, None, json.dumps({"error": repr(e)}).encode(), repr(e), {}


def parse_iso_date(value: str):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value).strip()[:10])
    except Exception:
        return None


def date_window(days: int, start_date: str = "", end_date: str = ""):
    """Return the controlled AQ26 date window.

    Normal weekly runs use lookback_days. Historical backfill runs must be date-bound,
    so explicit CLI dates or AQ26_WINDOW_START_DATE/AQ26_WINDOW_END_DATE win.
    The end date is treated as the public window label/date upper bound, matching the
    site archive convention used by AQ26 WeeklyV2.
    """
    env_start = os.getenv("AQ26_WINDOW_START_DATE") or os.getenv("AQ26_HISTORY_START_DATE") or os.getenv("AQ26_RUN_DATE_FROM")
    env_end = os.getenv("AQ26_WINDOW_END_DATE") or os.getenv("AQ26_HISTORY_END_DATE") or os.getenv("AQ26_RUN_DATE_TO")
    sd = parse_iso_date(start_date) or parse_iso_date(env_start)
    ed = parse_iso_date(end_date) or parse_iso_date(env_end)
    if sd and ed:
        if sd >= ed:
            raise ValueError(f"Invalid AQ26 date window: start {sd} must be before end {ed}")
        return sd.isoformat(), ed.isoformat()
    end = now_utc().date()
    start = end - dt.timedelta(days=int(days))
    return start.isoformat(), end.isoformat()


def metoffice_coord(v):
    return f"{float(v):.2f}"


def harvest_news(cfg, out, start_date):
    """Harvest optional news context with backfill-safe rate controls.

    News is useful context but not core scientific evidence. During historical
    backfill NewsAPI is disabled by default to avoid quota/rate-limit errors
    contaminating harvested evidence rows. GDELT remains optional, throttled and
    reduced to a small query set unless explicitly overridden.
    """
    global LAST_GDELT
    raw = mkdir(out / "03_news_context" / "raw")
    articles = []
    backfill = is_backfill_mode()
    newsapi_enabled = env_bool("AQ26_NEWSAPI_ENABLED", default=not backfill)
    newsdata_enabled = env_bool("AQ26_NEWSDATA_ENABLED", default=not backfill)
    gdelt_enabled = env_bool("AQ26_GDELT_ENABLED", default=True)
    query_limit = int(os.getenv("AQ26_BACKFILL_NEWS_QUERY_LIMIT", "3") if backfill else os.getenv("AQ26_NEWS_QUERY_LIMIT", "999"))
    gdelt_min_seconds = float(os.getenv("AQ26_GDELT_MIN_SECONDS", "6"))
    gdelt_retry_seconds = float(os.getenv("AQ26_GDELT_RETRY_SECONDS", "20"))

    newsapi = env_first("NEWS_API_KEY", "NEWSAPI_KEY")
    newsdata = env_first("NEWS_DATA_IO_KEY", "NEWSDATA_API_KEY", "NEWSDATA_KEY", "NEWSDATA_IO_KEY")
    queries = list(cfg.get("news_queries", []))[:max(0, query_limit)]

    if backfill and not newsapi_enabled:
        add_record("NewsAPI everything", "news_api", "newsapi://disabled-for-backfill", "historical_backfill", "skipped", None, None, 0, notes="disabled by AQ26_NEWSAPI_ENABLED default during historical backfill")
    if backfill and not newsdata_enabled:
        add_record("NewsData.io news", "news_api", "newsdata://disabled-for-backfill", "historical_backfill", "skipped", None, None, 0, notes="disabled by AQ26_NEWSDATA_ENABLED default during historical backfill")

    for q in queries:
        if newsapi and newsapi_enabled:
            url = "https://newsapi.org/v2/everything"
            params = {"q": q, "language": "en", "sortBy": "publishedAt", "pageSize": 25 if backfill else 50, "from": start_date, "apiKey": newsapi}
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(raw / f"newsapi_{slug(q)}_{RUN_TS}.json", content)
            status = "ok" if hs and hs < 400 else ("warning" if hs in (401, 403, 429) else "error")
            add_record("NewsAPI everything", "news_api" if status != "warning" else "news_api_warning", full_url(url, params), q, status, hs, p, count_records(data), err, notes="non-core contextual source; warning is non-blocking")
            if isinstance(data, dict) and isinstance(data.get("articles"), list):
                for item in data["articles"]:
                    item["_aq26_provider"] = "NewsAPI"
                    item["_aq26_query"] = q
                    articles.append(item)

        if newsdata and newsdata_enabled:
            url = "https://newsdata.io/api/1/news"
            params = {"apikey": newsdata, "q": q, "language": "en", "size": 10}
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(raw / f"newsdata_{slug(q)}_{RUN_TS}.json", content)
            status = "ok" if hs and hs < 400 else ("warning" if hs in (401, 403, 429) else "error")
            add_record("NewsData.io news", "news_api" if status != "warning" else "news_api_warning", full_url(url, params), q, status, hs, p, count_records(data), err, notes="non-core contextual source; warning is non-blocking")
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                for item in data["results"]:
                    item["_aq26_provider"] = "NewsData.io"
                    item["_aq26_query"] = q
                    articles.append(item)

        if gdelt_enabled:
            elapsed = time.time() - LAST_GDELT
            if elapsed < gdelt_min_seconds:
                time.sleep(gdelt_min_seconds - elapsed)
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            params = {"query": q, "mode": "ArtList", "format": "json", "maxrecords": 25 if backfill else 50, "sort": "HybridRel"}
            data, hs, content, err, _ = request_get(url, params=params, timeout=35)
            LAST_GDELT = time.time()
            if hs == 429:
                time.sleep(gdelt_retry_seconds)
                data, hs, content, err, _ = request_get(url, params=params, timeout=35)
                LAST_GDELT = time.time()
            p = write_bytes(raw / f"gdelt_{slug(q)}_{RUN_TS}.json", content)
            if hs and hs < 400:
                add_record("GDELT document API", "news_api", full_url(url, params), q, "ok", hs, p, count_records(data), err)
            else:
                add_warning("GDELT document API", q, hs, err, "Non-critical contextual provider warning; official/ground/satellite evidence remain primary.")
                add_record("GDELT document API", "news_api_warning", full_url(url, params), q, "warning", hs, p, count_records(data), err, notes="non-critical warning; throttled contextual source")

    write_json(out / "03_news_context" / "news_articles.json", {"run_ts": RUN_TS, "backfill_mode": backfill, "query_count": len(queries), "count": len(articles), "articles": articles})
    write_json(out / "03_news_context" / "news_provider_warnings.json", {"run_ts": RUN_TS, "warning_count": len(WARNINGS), "warnings": WARNINGS})


def harvest_ground_weather(cfg, out):
    raw = mkdir(out / "04_ground_aq_providers" / "raw")
    waqi = env_first("WAQI_TOKEN")
    ow = env_first("OPENWEATHER_KEY", "OW_KEY")
    met = env_first("MET_OFFICE_API_KEY", "METOFFICE_API_KEY", "MET_OFFICE_KEY")
    for site in cfg.get("sites", []):
        sid, lat, lon = site["id"], site["lat"], site["lon"]
        if waqi:
            url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
            params = {"token": waqi}
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(raw / f"waqi_{sid}_{RUN_TS}.json", content)
            add_record("WAQI geospatial feed", "ground_aq", full_url(url, params), sid, "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err)
        if ow:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {"lat": lat, "lon": lon, "appid": ow, "units": "metric"}
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(out / "05_weather" / "raw" / f"openweather_current_{sid}_{RUN_TS}.json", content)
            add_record("OpenWeather current weather", "weather", full_url(url, params), sid, "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err)
            url = "https://api.openweathermap.org/data/2.5/air_pollution"
            params = {"lat": lat, "lon": lon, "appid": ow}
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(raw / f"openweather_airpollution_{sid}_{RUN_TS}.json", content)
            add_record("OpenWeather air pollution", "ground_aq", full_url(url, params), sid, "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err)
    if met:
        focus = cfg.get("sites", [{"lat": 50.796, "lon": 0.055}])[0]
        url = "https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest"
        params = {"lat": metoffice_coord(focus.get("lat", 50.796)), "lon": metoffice_coord(focus.get("lon", 0.055))}
        data, hs, content, err, _ = request_get(url, params=params, headers={"apikey": met})
        p = write_bytes(out / "05_metoffice_datahub_weather" / f"metoffice_land_observations_{RUN_TS}.json", content)
        add_record("Met Office DataHub land observations", "weather", full_url(url, params), "newhaven_nearest", "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err, notes="apikey header; lat/lon rounded to 2dp")


def harvest_openaq(cfg, out):
    global LAST_OPENAQ
    ocfg = cfg.get("openaq", {})
    OPENAQ_SAFETY["enabled"] = os.getenv("AQ26_OPENAQ_ENABLED", "true").lower() in ("1", "true", "yes", "y") and ocfg.get("enabled", True)
    OPENAQ_SAFETY["max_requests_per_run"] = int(ocfg.get("max_requests_per_run", 8))
    OPENAQ_SAFETY["min_seconds_between_requests"] = float(ocfg.get("min_seconds_between_requests", 8))

    if not OPENAQ_SAFETY["enabled"]:
        OPENAQ_SAFETY["stopped_reason"] = "disabled"
        add_record("OpenAQ controlled harvest", "ground_aq", "openaq://disabled", "", "skipped", None, None, 0, notes="disabled")
        write_json(out / "04_ground_aq_providers" / "openaq_safety_manifest.json", OPENAQ_SAFETY)
        return

    key = env_first("OPENAQ_API_KEY")
    if not key:
        OPENAQ_SAFETY["stopped_reason"] = "missing_key"
        add_record("OpenAQ controlled harvest", "ground_aq", "https://api.openaq.org", "", "skipped", None, None, 0, notes="OPENAQ_API_KEY missing")
        write_json(out / "04_ground_aq_providers" / "openaq_safety_manifest.json", OPENAQ_SAFETY)
        return

    base = ocfg.get("base_url", "https://api.openaq.org").rstrip("/")
    headers = {"X-API-Key": key, "User-Agent": ocfg.get("user_agent", "AQ26-WeeklyV2-controlled-review/1.0"), "Accept": "application/json"}
    raw = mkdir(out / "04_ground_aq_providers" / "openaq_raw")

    for site in cfg.get("sites", []):
        if OPENAQ_SAFETY["request_count"] >= OPENAQ_SAFETY["max_requests_per_run"]:
            OPENAQ_SAFETY["stopped_reason"] = "max_requests_reached"
            break

        elapsed = time.time() - LAST_OPENAQ
        if elapsed < OPENAQ_SAFETY["min_seconds_between_requests"]:
            time.sleep(OPENAQ_SAFETY["min_seconds_between_requests"] - elapsed)

        url = f"{base}/v3/locations"
        params = {
            "coordinates": f"{site['lat']},{site['lon']}",
            "radius": int(ocfg.get("radius_m", 25000)),
            "limit": int(ocfg.get("limit", 100)),
        }
        data, hs, content, err, hdrs = request_get(url, params=params, headers=headers, timeout=35)
        LAST_OPENAQ = time.time()
        OPENAQ_SAFETY["request_count"] += 1
        OPENAQ_SAFETY["status_codes"].append(hs)
        OPENAQ_SAFETY["site_ids"].append(site["id"])

        p = write_bytes(raw / f"openaq_locations_{site['id']}_{RUN_TS}.json", content)
        add_record("OpenAQ v3 locations radius search", "ground_aq", full_url(url, params), site["id"], "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err, notes=f"strict cap {OPENAQ_SAFETY['request_count']}/{OPENAQ_SAFETY['max_requests_per_run']}; no pagination")

        if hs in (401, 403):
            OPENAQ_SAFETY["auth_error_seen"] = True
            OPENAQ_SAFETY["stopped_reason"] = f"auth_stop_{hs}"
            break
        if hs == 429:
            OPENAQ_SAFETY["rate_limit_seen"] = True
            OPENAQ_SAFETY["stopped_reason"] = f"rate_limit_stop_retry_after_{hdrs.get('Retry-After','')}"
            break

    if not OPENAQ_SAFETY["stopped_reason"]:
        OPENAQ_SAFETY["stopped_reason"] = "completed_low_rate_plan"
    write_json(out / "04_ground_aq_providers" / "openaq_safety_manifest.json", OPENAQ_SAFETY)


def harvest_cams(cfg, out, start_date, end_date):
    key = env_first("CAMS_API_KEY")
    base_url = env_first("CAMS_BASE_URL", "CAMS_ENDPOINT")
    cams_cfg = cfg.get("cams", {})
    readiness = {
        "run_ts": RUN_TS,
        "cams_key_present": bool(key),
        "cams_endpoint_configured": bool(base_url),
        "cams_data_ready": False,
        "variables_requested": cams_cfg.get("variables", []),
        "date_window": {"start": start_date, "end": end_date},
        "notes": "CAMS is not called unless CAMS_BASE_URL is configured. This avoids guessing endpoints.",
    }

    if os.getenv("AQ26_CAMS_ENABLED", "true").lower() not in ("1", "true", "yes", "y"):
        readiness["status"] = "disabled"
        p = write_json(out / "09_cams" / "cams_readiness.json", readiness)
        add_record("CAMS readiness", "atmospheric_model", "cams://disabled", "readiness", "skipped", None, p, 1, notes="disabled")
        return

    if not key:
        readiness["status"] = "missing_key"
        p = write_json(out / "09_cams" / "cams_readiness.json", readiness)
        add_record("CAMS readiness", "atmospheric_model", "cams://missing-key", "readiness", "skipped", None, p, 1, notes="CAMS_API_KEY missing")
        return

    if not base_url:
        readiness["status"] = "key_present_endpoint_missing"
        p = write_json(out / "09_cams" / "cams_readiness.json", readiness)
        add_record("CAMS readiness", "atmospheric_model", "cams://configured-key-no-endpoint", "readiness", "ok", None, p, 1, notes="CAMS key present; no data call attempted")
        return

    params = {"start": start_date, "end": end_date, "apikey": key}
    data, hs, content, err, _ = request_get(base_url, params=params, timeout=45)
    p = write_bytes(out / "09_cams" / f"cams_response_{RUN_TS}.json", content)
    readiness["status"] = "data_response_ok" if hs and hs < 400 else "data_response_error"
    readiness["http_status"] = hs
    readiness["cams_data_ready"] = bool(hs and hs < 400)
    write_json(out / "09_cams" / "cams_readiness.json", readiness)
    add_record("CAMS configured endpoint", "atmospheric_model", full_url(base_url, params), "configured_endpoint", "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err, notes="CAMS_BASE_URL configured by secret")


def harvest_official(cfg, out):
    raw = mkdir(out / "06_official_filings" / "raw")
    filings = []
    for q in cfg.get("official_queries", []):
        for source, url, params in [
            ("GOV.UK", "https://www.gov.uk/api/search.json", {"q": q, "count": 50}),
            ("data.gov.uk", "https://ckan.publishing.service.gov.uk/api/3/action/package_search", {"q": q, "rows": 50}),
        ]:
            data, hs, content, err, _ = request_get(url, params=params)
            p = write_bytes(raw / f"{slug(source)}_{slug(q)}_{RUN_TS}.json", content)
            add_record(f"{source} search", "official_search", full_url(url, params), q, "ok" if hs and hs < 400 else "error", hs, p, count_records(data), err)
            if source == "GOV.UK" and isinstance(data, dict):
                for row in data.get("results", []):
                    filings.append({"source": source, "query": q, "title": row.get("title"), "url": urllib.parse.urljoin("https://www.gov.uk", row.get("link", "")), "raw": row})
            if source == "data.gov.uk" and isinstance(data, dict) and isinstance(data.get("result"), dict):
                for row in data["result"].get("results", []):
                    filings.append({"source": source, "query": q, "title": row.get("title"), "url": row.get("url") or "", "raw": row})

    for item in cfg.get("watch_urls", []):
        data, hs, content, err, _ = request_get(item["url"])
        p = write_bytes(raw / f"watch_{slug(item.get('name','watch'))}_{RUN_TS}.html", content)
        add_record(item.get("name", "Watch URL"), "official_watch_url", item["url"], item.get("name", ""), "ok" if hs and hs < 400 else "error", hs, p, 1 if hs and hs < 400 else 0, err)
        filings.append({"source": "watch_url", "query": item.get("name"), "title": item.get("name"), "url": item["url"], "raw_path": str(p)})

    high_terms = [x.lower() for x in cfg.get("scoring", {}).get("high_terms", [])]
    pollutant_terms = [x.lower() for x in cfg.get("scoring", {}).get("pollutant_terms", [])]
    for f in filings:
        text = json.dumps(f, ensure_ascii=False).lower()
        h = [x for x in high_terms if x in text]
        p = [x for x in pollutant_terms if x in text]
        score = len(h) * 5 + len(p) * 2
        f["aq26_score"] = score
        f["aq26_priority"] = "high" if score >= 10 else ("medium" if score >= 4 else ("low" if score else "weak_or_irrelevant"))
        f["aq26_high_hits"] = h
        f["aq26_pollutant_hits"] = p

    write_json(out / "06_official_filings" / "official_filing_index.json", {"run_ts": RUN_TS, "filing_count": len(filings), "filings": filings})
    write_json(out / "06_official_filings" / "official_priority_summary.json", {
        "run_ts": RUN_TS,
        "high": [f for f in filings if f.get("aq26_priority") == "high"][:100],
        "medium": [f for f in filings if f.get("aq26_priority") == "medium"][:150],
        "counts": {k: sum(1 for f in filings if f.get("aq26_priority") == k) for k in ["high", "medium", "low", "weak_or_irrelevant"]},
    })


def harvest_satellite(cfg, out, start_date, end_date):
    raw = mkdir(out / "07_satellite_cdse" / "raw")
    scfg = cfg.get("satellite", {})
    bbox = scfg.get("bbox", [-0.15, 50.68, 0.35, 50.95])
    meta = {"run_ts": RUN_TS, "bbox": bbox, "start_date": start_date, "end_date": end_date, "odata": [], "product_count": 0, "extraction_ready": False}
    base = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    for product in scfg.get("odata_products", []):
        flt = f"contains(Name,'S5P') and contains(Name,'{product}') and ContentDate/Start ge {start_date}T00:00:00.000Z and ContentDate/Start le {end_date}T23:59:59.000Z"
        params = {"$filter": flt, "$top": int(scfg.get("max_records_per_product", 50)), "$orderby": "ContentDate/Start desc"}
        data, hs, content, err, _ = request_get(base, params=params, timeout=35)
        p = write_bytes(raw / f"copernicus_odata_{product}_{RUN_TS}.json", content)
        c = count_records(data)
        meta["odata"].append({"product": product, "http_status": hs, "count": c, "path": str(p), "bbox_context": bbox})
        meta["product_count"] += c
        add_record("Copernicus Data Space OData product search", "satellite_metadata", full_url(base, params), product, "ok" if hs and hs < 400 else "error", hs, p, c, err, notes="catalogue only; not pollutant extraction")
    write_json(out / "07_satellite_cdse" / "satellite_catalogue_metadata.json", meta)
    write_json(out / "07_satellite_cdse" / "satellite_extraction_plan.json", {
        "run_ts": RUN_TS,
        "status": "planned_not_executed",
        "products": scfg.get("odata_products", []),
        "next_stage": "download selected products, extract NO2/SO2/CO/HCHO/O3/CH4/AER_AI variables, apply QA flags, align with wind sector and ground/control sites",
    })


def harvest_gdrive(out):
    if os.getenv("AQ26_SYNC_GOOGLE_DRIVE", "true").lower() not in ("1", "true", "yes", "y"):
        add_record("Google Drive inventory", "gdrive", "gdrive://disabled", "", "skipped", None, None, 0)
        return
    folder_id = env_first("GDRIVE_FOLDER_ID")
    cred = env_first("GDRIVE_SERVICE_ACCOUNT", "GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS")
    if not folder_id or not cred:
        add_record("Google Drive inventory", "gdrive", "gdrive://missing", "", "skipped", None, None, 0, notes="missing folder id or service account")
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info = json.loads(cred)
        creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        files, queue, seen = [], [(folder_id, "ROOT", 0)], set()
        max_files = 5000 if os.getenv("AQ26_RECURSIVE_DRIVE_SCAN", "true").lower() in ("1", "true", "yes", "y") else 1000
        folder_count = 0
        shortcut_count = 0
        shortcut_folders_followed = 0
        while queue and len(files) < max_files:
            fid, path_prefix, depth = queue.pop(0)
            if fid in seen or depth > 7:
                continue
            seen.add(fid)
            token = None
            while True:
                resp = svc.files().list(
                    q=f"'{fid}' in parents and trashed=false",
                    fields="nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,webViewLink,parents,shortcutDetails)",
                    pageSize=1000, pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True
                ).execute()
                for item in resp.get("files", []):
                    path = f"{path_prefix}/{item.get('name','')}"
                    is_folder = item.get("mimeType") == "application/vnd.google-apps.folder"
                    is_shortcut = item.get("mimeType") == "application/vnd.google-apps.shortcut"
                    if is_folder:
                        folder_count += 1
                    if is_shortcut:
                        shortcut_count += 1
                    files.append({
                        "path": path, "id_hash": hashlib.sha256(item.get("id", "").encode()).hexdigest()[:12],
                        "name": item.get("name"), "mimeType": item.get("mimeType"), "modifiedTime": item.get("modifiedTime"),
                        "createdTime": item.get("createdTime"), "size": item.get("size"), "md5Checksum": item.get("md5Checksum"),
                        "webViewLink": item.get("webViewLink"), "depth": depth + 1, "is_folder": is_folder, "is_shortcut": is_shortcut
                    })
                    if is_folder:
                        queue.append((item["id"], path, depth + 1))
                    if is_shortcut:
                        sd = item.get("shortcutDetails") or {}
                        if sd.get("targetId") and sd.get("targetMimeType") == "application/vnd.google-apps.folder":
                            shortcut_folders_followed += 1
                            queue.append((sd["targetId"], path + " -> shortcut_target", depth + 1))
                    if len(files) >= max_files:
                        break
                token = resp.get("nextPageToken")
                if not token or len(files) >= max_files:
                    break
        inventory = {
            "run_ts": RUN_TS,
            "file_count": len(files),
            "max_files": max_files,
            "drive_inventory_truncated": len(files) >= max_files,
            "folder_count": folder_count,
            "shortcut_count": shortcut_count,
            "shortcut_folders_followed": shortcut_folders_followed,
            "files": files,
        }
        p = write_json(out / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json", inventory)
        add_record("Google Drive recursive inventory", "gdrive", f"gdrive://{folder_id}", "recursive", "ok", None, p, len(files), notes="metadata only; file IDs hashed")
    except Exception as e:
        p = write_json(out / "08_gdrive_snapshot" / "gdrive_error.json", {"error": repr(e)})
        add_record("Google Drive recursive inventory", "gdrive", f"gdrive://{folder_id}", "recursive", "error", None, p, 0, repr(e))



def harvest_purpleair(cfg, out):
    pcfg = cfg.get("optional_sources", {}).get("purpleair", {})
    key = env_first("PURPLE_AIR_API_KEY", "PURPLEAIR_API_KEY")
    if not pcfg.get("enabled", True):
        add_record("PurpleAir readiness", "low_cost_sensor_context", "purpleair://disabled", "readiness", "skipped", None, None, 0, notes="disabled in config")
        return
    if not key:
        p = write_json(out / "15_optional_sources" / "purpleair_readiness.json", {
            "run_ts": RUN_TS, "purpleair_key_present": False, "purpleair_data_ready": False,
            "notes": "PURPLE_AIR_API_KEY missing."
        })
        add_record("PurpleAir readiness", "low_cost_sensor_context", "purpleair://missing-key", "readiness", "skipped", None, p, 1, notes="PURPLE_AIR_API_KEY missing")
        return
    url = pcfg.get("base_url", "https://api.purpleair.com/v1/sensors")
    # Conservative metadata-only regional query. If PurpleAir changes API semantics, failure is recorded but not critical.
    params = {
        "fields": "sensor_index,name,latitude,longitude,last_seen,pm2.5_atm,pm2.5_cf_1",
        "location_type": 0,
        "nwlng": -0.20, "nwlat": 50.98, "selng": 0.40, "selat": 50.65,
        "max_age": 604800,
    }
    headers = {"X-API-Key": key, "Accept": "application/json"}
    data, hs, content, err, _ = request_get(url, params=params, headers=headers, timeout=35)
    p = write_bytes(out / "15_optional_sources" / f"purpleair_sensors_{RUN_TS}.json", content)
    status = "ok" if hs and hs < 400 else "warning"
    if status == "warning":
        add_warning("PurpleAir sensors", "regional_context", hs, err, "Optional low-cost sensor provider warning.")
    add_record("PurpleAir sensors regional context", "low_cost_sensor_context", full_url(url, params), "regional_context", status, hs, p, count_records(data), err, notes="optional; contextual only, not reference-grade")


def harvest_serpapi(cfg, out):
    scfg = cfg.get("optional_sources", {}).get("serpapi", {})
    key = env_first("SERPAPI_API_KEY")
    if not scfg.get("enabled", True):
        add_record("SerpAPI readiness", "web_search_context", "serpapi://disabled", "readiness", "skipped", None, None, 0, notes="disabled in config")
        return
    if not key:
        p = write_json(out / "15_optional_sources" / "serpapi_readiness.json", {
            "run_ts": RUN_TS, "serpapi_key_present": False, "serpapi_data_ready": False,
            "notes": "SERPAPI_API_KEY missing."
        })
        add_record("SerpAPI readiness", "web_search_context", "serpapi://missing-key", "readiness", "skipped", None, p, 1, notes="SERPAPI_API_KEY missing")
        return
    raw = mkdir(out / "15_optional_sources" / "serpapi_raw")
    url = scfg.get("base_url", "https://serpapi.com/search.json")
    max_req = int(scfg.get("max_requests_per_run", 3))
    for i, q in enumerate(scfg.get("queries", [])[:max_req], start=1):
        params = {"engine": "google", "q": q, "api_key": key, "num": 10}
        data, hs, content, err, _ = request_get(url, params=params, timeout=35)
        p = write_bytes(raw / f"serpapi_{slug(q)}_{RUN_TS}.json", content)
        status = "ok" if hs and hs < 400 else "warning"
        if status == "warning":
            add_warning("SerpAPI Google search", q, hs, err, "Optional web discovery provider warning.")
        add_record("SerpAPI Google search", "web_search_context", full_url(url, params), q, status, hs, p, count_records(data), err, notes=f"optional search context {i}/{max_req}")


def harvest_earthdata(cfg, out, start_date, end_date):
    ecfg = cfg.get("optional_sources", {}).get("earthdata", {})
    token = env_first("EARTH_DATA_API_KEY", "EARTHDATA_API_KEY", "NASA_EARTHDATA_TOKEN")
    if not ecfg.get("enabled", True):
        add_record("NASA Earthdata CMR readiness", "satellite_metadata", "earthdata://disabled", "readiness", "skipped", None, None, 0, notes="disabled in config")
        return
    raw = mkdir(out / "15_optional_sources" / "earthdata_raw")
    readiness = {
        "run_ts": RUN_TS,
        "earthdata_key_present": bool(token),
        "earthdata_cmr_ready": False,
        "date_window": {"start": start_date, "end": end_date},
        "notes": "CMR discovery only. No Earthdata file download/extraction in WeeklyV2."
    }
    url = ecfg.get("cmr_base_url", "https://cmr.earthdata.nasa.gov/search/granules.json")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    total_records = 0
    for short_name in ecfg.get("short_names", [])[: int(ecfg.get("max_requests_per_run", 2))]:
        params = {
            "short_name": short_name,
            "temporal": f"{start_date}T00:00:00Z,{end_date}T23:59:59Z",
            "bounding_box": "-0.15,50.68,0.35,50.95",
            "page_size": 10,
        }
        data, hs, content, err, _ = request_get(url, params=params, headers=headers, timeout=35)
        p = write_bytes(raw / f"earthdata_cmr_{slug(short_name)}_{RUN_TS}.json", content)
        c = count_records(data)
        total_records += c
        status = "ok" if hs and hs < 400 else "warning"
        if status == "warning":
            add_warning("NASA Earthdata CMR", short_name, hs, err, "Optional NASA CMR discovery warning.")
        add_record("NASA Earthdata CMR granules", "satellite_metadata", full_url(url, params), short_name, status, hs, p, c, err, notes="optional discovery only")
    readiness["earthdata_cmr_ready"] = total_records > 0
    readiness["record_count"] = total_records
    write_json(out / "15_optional_sources" / "earthdata_readiness.json", readiness)


def harvest_cdse_auth_readiness(cfg, out):
    ccfg = cfg.get("optional_sources", {}).get("cdse_auth", {})
    if not ccfg.get("enabled", True):
        add_record("CDSE auth readiness", "satellite_auth", "cdse://disabled", "readiness", "skipped", None, None, 0, notes="disabled in config")
        return

    # AQ26 V3.2.1: support the repository's existing secret names and the
    # alternative names used by some Copernicus/CDSE examples. Scott confirmed
    # CDSE_USERNAME + CDSE_PASSWORD have worked previously, so test that path
    # first before attempting client-credentials aliases.
    username = env_first("CDSE_USERNAME")
    password = env_first("CDSE_PASSWORD")
    client_id = env_first("CDSE_ID", "CDSE_CLIENT_ID")
    client_secret = env_first("CDSE_SECRET", "CDSE_CLIENT_SECRET")
    token_url = ccfg.get("token_url", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token")
    readiness = {
        "run_ts": RUN_TS,
        "cdse_username_present": bool(username),
        "cdse_password_present": bool(password),
        "cdse_client_id_present": bool(client_id),
        "cdse_client_secret_present": bool(client_secret),
        "cdse_username_password_ready": False,
        "cdse_client_credentials_ready": False,
        "cdse_token_ready": False,
        "token_probe_attempted": False,
        "auth_method_attempted": [],
        "http_status": None,
        "notes": "No token value is stored. WeeklyV2 probes readiness only; product download/extraction is a later gate."
    }

    def _post_token(method_name, data):
        readiness["token_probe_attempted"] = True
        readiness["auth_method_attempted"].append(method_name)
        try:
            r = requests.post(token_url, data=data, timeout=30)
            readiness["http_status"] = r.status_code
            if r.ok:
                js = r.json()
                if js.get("access_token"):
                    readiness["cdse_token_ready"] = True
                    readiness["expires_in"] = js.get("expires_in")
                    readiness["auth_method_success"] = method_name
                    return True
                readiness["error"] = "Token response did not include access_token"
            else:
                readiness["error"] = redact(r.text[:500])
        except Exception as exc:
            readiness["error"] = redact(repr(exc))
        return False

    # 1) Known-good AQ26 path: username/password with public client. Try
    # cdse-public first; if user supplied CDSE_ID and it differs, try that too.
    if username and password:
        client_candidates = []
        for cid in ["cdse-public", client_id]:
            if cid and cid not in client_candidates:
                client_candidates.append(cid)
        for cid in client_candidates:
            ok = _post_token("username_password", {
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": cid,
            })
            if ok:
                readiness["cdse_username_password_ready"] = True
                break

    # 2) Fallback alias path: CDSE_ID/CDSE_SECRET or CDSE_CLIENT_ID/CDSE_CLIENT_SECRET.
    if not readiness.get("cdse_token_ready") and client_id and client_secret:
        ok = _post_token("client_credentials", {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        })
        readiness["cdse_client_credentials_ready"] = bool(ok)

    p = write_json(out / "15_optional_sources" / "cdse_auth_readiness.json", readiness)
    add_record("CDSE auth readiness", "satellite_auth", token_url, "token_probe", "ok" if readiness.get("cdse_token_ready") else "warning", readiness.get("http_status"), p, 1, readiness.get("error", ""), notes="auth probe order: CDSE_USERNAME/CDSE_PASSWORD then CDSE_ID/CDSE_SECRET aliases; token is not stored")


def harvest_gemini_summary(cfg, out):
    gcfg = cfg.get("optional_sources", {}).get("gemini", {})
    backfill = is_backfill_mode()
    key = env_first("GEMINI_API_KEY")
    model = env_first("AQ26_GEMINI_MODEL", "GEMINI_MODEL") or "gemini-3.5-flash"
    summary_input = {
        "run_ts": RUN_TS,
        "records": len(RECORDS),
        "ok": sum(1 for r in RECORDS if r.get("status") == "ok"),
        "warning": sum(1 for r in RECORDS if r.get("status") == "warning"),
        "error": sum(1 for r in RECORDS if r.get("status") == "error"),
        "source_types": sorted(set(r.get("source_type", "") for r in RECORDS)),
        "controlled_use_boundary": "Neutral metadata-only summary. No raw evidence, no API keys, no causal attribution.",
    }
    enabled = env_bool("AQ26_GEMINI_ENABLED", default=bool(gcfg.get("enabled", False if backfill else True)))
    if not enabled:
        add_record("Gemini neutral metadata summary", "ai_summary", "gemini://disabled", "summary", "skipped", None, None, 0, notes="disabled for historical backfill unless AQ26_GEMINI_ENABLED=true")
        return
    if not key:
        p = write_json(out / "14_ai" / "gemini_summary.json", {
            "run_ts": RUN_TS, "gemini_key_present": False, "gemini_summary_ready": False,
            "input_summary": summary_input
        })
        add_record("Gemini neutral metadata summary", "ai_summary", "gemini://missing-key", "summary", "skipped", None, p, 1, notes="GEMINI_API_KEY missing")
        return
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        "Produce a concise neutral controlled-review metadata summary for an air-quality evidence harvest. "
        "Do not claim causation, endorsement, or external validation. Metadata only:\n"
        + json.dumps(summary_input, ensure_ascii=False)
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    params = {"key": key}
    try:
        r = requests.post(url, params=params, json=payload, timeout=45)
        result = {
            "run_ts": RUN_TS, "gemini_key_present": True, "gemini_model": model,
            "gemini_summary_ready": bool(r.ok), "http_status": r.status_code,
            "input_summary": summary_input
        }
        if r.ok:
            js = r.json()
            text = ""
            try:
                text = js["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                text = ""
            result["summary_text"] = text[:5000]
        else:
            result["error"] = redact(r.text[:1000])
        p = write_json(out / "14_ai" / "gemini_summary.json", result)
        add_record("Gemini neutral metadata summary", "ai_summary", full_url(url, params), "metadata_summary", "ok" if r.ok else "warning", r.status_code, p, 1, result.get("error", ""), notes="metadata-only AI summary; no raw evidence or secrets")
    except Exception as exc:
        p = write_json(out / "14_ai" / "gemini_summary.json", {
            "run_ts": RUN_TS, "gemini_key_present": True, "gemini_summary_ready": False,
            "gemini_model": model, "error": redact(repr(exc)), "input_summary": summary_input
        })
        add_record("Gemini neutral metadata summary", "ai_summary", "gemini://exception", "metadata_summary", "warning", None, p, 1, repr(exc), notes="metadata-only AI summary exception")

def build_backfill_and_gates(cfg, out, start_date, end_date):
    expected = ["news_api", "ground_aq", "weather", "official_search", "official_watch_url", "satellite_metadata", "gdrive", "atmospheric_model", "low_cost_sensor_context", "web_search_context", "satellite_auth", "ai_summary"]
    observed = {k: any(r.get("source_type") == k and r.get("status") == "ok" for r in RECORDS) for k in expected}
    cams_readiness = {}
    cams_path = out / "09_cams" / "cams_readiness.json"
    if cams_path.exists():
        cams_readiness = json.loads(cams_path.read_text(encoding="utf-8"))
    drive_inventory = {}
    drive_path = out / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json"
    if drive_path.exists():
        drive_inventory = json.loads(drive_path.read_text(encoding="utf-8"))
    earthdata_readiness = {}
    earthdata_path = out / "15_optional_sources" / "earthdata_readiness.json"
    if earthdata_path.exists():
        earthdata_readiness = json.loads(earthdata_path.read_text(encoding="utf-8"))
    cdse_auth = {}
    cdse_path = out / "15_optional_sources" / "cdse_auth_readiness.json"
    if cdse_path.exists():
        cdse_auth = json.loads(cdse_path.read_text(encoding="utf-8"))
    gemini_summary = {}
    gemini_path = out / "14_ai" / "gemini_summary.json"
    if gemini_path.exists():
        gemini_summary = json.loads(gemini_path.read_text(encoding="utf-8"))
    gates = {
        "automation_ready": True,
        "provenance_ready": True,
        "redaction_ready": None,
        "metoffice_ready": any(r["source_name"] == "Met Office DataHub land observations" and r["status"] == "ok" for r in RECORDS),
        "ground_aq_ready": observed["ground_aq"],
        "openaq_ready": any(r["source_name"].startswith("OpenAQ") and r["status"] == "ok" for r in RECORDS),
        "openaq_safety_ready": OPENAQ_SAFETY["enabled"] and not OPENAQ_SAFETY["rate_limit_seen"] and not OPENAQ_SAFETY["auth_error_seen"],
        "cams_key_present": bool(cams_readiness.get("cams_key_present")),
        "cams_endpoint_configured": bool(cams_readiness.get("cams_endpoint_configured")),
        "cams_data_ready": bool(cams_readiness.get("cams_data_ready")),
        "satellite_catalogue_ready": observed["satellite_metadata"],
        "satellite_extraction_ready": False,
        "official_filings_ready": observed["official_search"],
        "drive_ready": observed["gdrive"],
        "drive_inventory_truncated": bool(drive_inventory.get("drive_inventory_truncated")),
        "purpleair_context_ready": observed["low_cost_sensor_context"],
        "serpapi_context_ready": observed["web_search_context"],
        "earthdata_key_present": bool(earthdata_readiness.get("earthdata_key_present")),
        "earthdata_cmr_ready": bool(earthdata_readiness.get("earthdata_cmr_ready")),
        "cdse_auth_ready": bool(cdse_auth.get("cdse_token_ready")),
        "gemini_summary_ready": bool(gemini_summary.get("gemini_summary_ready")),
        "backfill_ready": True,
        "external_submission_ready": False,
        "blocking_reasons": [
            "External submission remains false until satellite pollutant extraction, official document review, ground QA, wind-sector analysis and uncertainty gates pass."
        ],
    }
    missing = [{"stream": k, "status": "missing_or_failed", "priority": "high" if k in ["ground_aq", "weather", "satellite_metadata"] else "medium"} for k, v in observed.items() if not v]
    write_json(out / "11_backfill" / "missing_date_backfill_plan.json", {"run_ts": RUN_TS, "window": {"start": start_date, "end": end_date}, "missing_count": len(missing), "missing": missing})
    write_json(out / "12_scoring" / "evidence_readiness_gates.json", gates)
    write_json(out / "12_scoring" / "evidence_priority_scores.json", {
        "run_ts": RUN_TS,
        "methods_alignment": {
            "dominici": "Causal language guarded; exposure/confounder/backfill readiness only.",
            "martin": "Satellite catalogue supports remote-sensing context; extraction and ground-fusion next.",
            "brauer": "Multi-source exposure-screening registry; no health-burden attribution yet.",
            "anenberg": "NO2/SO2/CO/HCHO/O3/CH4/AER_AI trace-gas families prioritised.",
            "damoulas": "Target/control graph, Drive inventory, gaps and alerts support digital-twin readiness.",
            "optional_sources": "PurpleAir, SerpAPI, Earthdata CMR, CDSE auth and Gemini are integrated as cautious optional metadata/readiness streams."
        }
    })


def finish(out, cfg, start_date, end_date):
    mkdir(out / "source_history")
    with (out / "source_history" / "source_index.jsonl").open("a", encoding="utf-8") as f:
        for r in RECORDS:
            f.write(json.dumps(safe_json(r), ensure_ascii=False) + "\n")
    latest = {
        "run_ts": RUN_TS, "date_window": {"start": start_date, "end": end_date},
        "project": cfg.get("project", {}).get("name", "SCCNEXUS AirQuality26 WeeklyV2"),
        "controlled_use_boundary": cfg.get("project", {}).get("controlled_use_boundary", ""),
        "source_record_count": len(RECORDS), "ok_count": sum(1 for r in RECORDS if r["status"] == "ok"),
        "error_count": sum(1 for r in RECORDS if r["status"] == "error"),
        "warning_count": sum(1 for r in RECORDS if r["status"] == "warning"),
        "skipped_count": sum(1 for r in RECORDS if r["status"] == "skipped"),
        "source_records": RECORDS
    }
    write_json(out / "00_weeklyv2" / "LATEST_WEEKLYV2.json", latest)
    write_json(out / "00_live_harvest" / "LATEST_HARVEST.json", latest)
    run_dir = mkdir(out / "00_weeklyv2" / f"AQ26_WEEKLYV2_{RUN_TS}")
    write_json(run_dir / f"AQ26_WEEKLYV2_MANIFEST_{RUN_TS}.json", latest)
    if RECORDS:
        with (run_dir / f"AQ26_WEEKLYV2_SOURCE_RECORDS_{RUN_TS}.csv").open("w", newline="", encoding="utf-8") as f:
            fieldnames = sorted({k for r in RECORDS for k in r.keys()})
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(RECORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/aq26_weekly_v2_sources.yml")
    ap.add_argument("--output-root", default="outputs")
    ap.add_argument("--lookback-days", default="14")
    ap.add_argument("--start-date", default="", help="Explicit historical window start date YYYY-MM-DD. Overrides lookback-days.")
    ap.add_argument("--end-date", default="", help="Explicit historical window end date YYYY-MM-DD. Overrides lookback-days.")
    args = ap.parse_args()
    out = Path(args.output_root)
    mkdir(out)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    start_date, end_date = date_window(int(args.lookback_days), args.start_date, args.end_date)
    harvest_news(cfg, out, start_date)
    harvest_ground_weather(cfg, out)
    harvest_openaq(cfg, out)
    harvest_cams(cfg, out, start_date, end_date)
    harvest_purpleair(cfg, out)
    harvest_serpapi(cfg, out)
    harvest_earthdata(cfg, out, start_date, end_date)
    harvest_cdse_auth_readiness(cfg, out)
    harvest_official(cfg, out)
    harvest_satellite(cfg, out, start_date, end_date)
    harvest_gdrive(out)
    harvest_gemini_summary(cfg, out)
    build_backfill_and_gates(cfg, out, start_date, end_date)
    finish(out, cfg, start_date, end_date)
    print(json.dumps({
        "run_ts": RUN_TS,
        "records": len(RECORDS),
        "ok": sum(1 for r in RECORDS if r["status"] == "ok"),
        "errors": sum(1 for r in RECORDS if r["status"] == "error"),
        "warnings": sum(1 for r in RECORDS if r["status"] == "warning"),
        "skipped": sum(1 for r in RECORDS if r["status"] == "skipped")
    }, indent=2))


if __name__ == "__main__":
    main()
