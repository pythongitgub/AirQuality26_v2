#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:
    yaml = None

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "USERNAME", "CLIENT")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_ts() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Add pyyaml to the workflow install step.")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(text: str, limit: int = 120) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("._")
    return (text or "item")[:limit]


def redacted_env_status(names: list[str]) -> dict[str, str]:
    out = {}
    for name in names:
        value = os.getenv(name, "")
        out[name] = f"SET_REDACTED_len_{len(value)}" if value else "EMPTY"
    return out


@dataclass
class SourceRecord:
    run_ts: str
    source_name: str
    source_type: str
    url: str
    query: str = ""
    status: str = "not_started"
    http_status: int | None = None
    retrieved_at_utc: str = ""
    retrieved_at_uk: str = ""
    date_uk: str = ""
    output_path: str = ""
    sha256: str = ""
    bytes: int = 0
    record_count: int | None = None
    error: str = ""
    notes: str = ""


def uk_time_fields(dt: datetime) -> tuple[str, str]:
    if ZoneInfo is None:
        return dt.isoformat(), dt.strftime("%d/%m/%Y")
    uk = dt.astimezone(ZoneInfo("Europe/London"))
    return uk.isoformat(), uk.strftime("%d/%m/%Y")


class Harvester:
    def __init__(self, cfg: dict[str, Any], output_root: Path, lookback_days: int, download_official_files: bool):
        self.cfg = cfg
        self.output_root = output_root
        self.lookback_days = lookback_days
        self.download_official_files = download_official_files
        self.ts = run_ts()
        self.harvest_root = ensure_dir(output_root / "00_live_harvest" / f"AQ26_LIVE_HARVEST_{self.ts}")
        self.news_dir = ensure_dir(output_root / "03_news_context")
        self.ground_dir = ensure_dir(output_root / "04_ground_aq_providers")
        self.weather_dir = ensure_dir(output_root / "05_metoffice_datahub_weather")
        self.official_dir = ensure_dir(output_root / "06_official_filings")
        self.sat_dir = ensure_dir(output_root / "07_satellite_cdse" / "raw")
        self.history_dir = ensure_dir(output_root / "source_history")
        self.download_dir = ensure_dir(self.official_dir / "downloads")
        self.records: list[SourceRecord] = []
        self.user_agent = cfg.get("user_agent", "AQ26-GitHub-Weekly-Report/1.0")

    def write_json(self, path: Path, obj: Any) -> Path:
        ensure_dir(path.parent)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def request_json(self, source_name: str, source_type: str, url: str, *, query: str = "", headers: dict[str, str] | None = None, timeout: int = 30, method: str = "GET", body: bytes | None = None) -> tuple[Any | None, SourceRecord]:
        dt = utc_now(); uk_iso, date_uk = uk_time_fields(dt)
        rec = SourceRecord(self.ts, source_name, source_type, url, query=query, retrieved_at_utc=dt.isoformat(), retrieved_at_uk=uk_iso, date_uk=date_uk)
        req_headers = {"User-Agent": self.user_agent, "Accept": "application/json,text/plain,*/*"}
        if headers:
            req_headers.update(headers)
        try:
            req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                rec.http_status = getattr(resp, "status", None)
                rec.status = "ok"
                rec.bytes = len(raw)
                rec.sha256 = sha256_bytes(raw)
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype or raw[:1] in (b"{", b"["):
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                else:
                    data = {"raw_text": raw.decode("utf-8", errors="replace")[:200000], "content_type": ctype}
                return data, rec
        except Exception as e:
            rec.status = "error"
            rec.error = repr(e)
            return None, rec

    def save_response(self, rec: SourceRecord, data: Any, out_path: Path, count: int | None = None) -> None:
        self.write_json(out_path, {"provenance": asdict(rec), "data": data})
        rec.output_path = str(out_path)
        rec.bytes = out_path.stat().st_size
        rec.sha256 = sha256_file(out_path)
        if count is not None:
            rec.record_count = count
        self.records.append(rec)

    def save_error_record(self, rec: SourceRecord, out_path: Path) -> None:
        self.write_json(out_path, {"provenance": asdict(rec), "data": None})
        rec.output_path = str(out_path)
        rec.bytes = out_path.stat().st_size
        rec.sha256 = sha256_file(out_path)
        self.records.append(rec)

    def harvest_news(self) -> None:
        articles: list[dict[str, Any]] = []
        kept: list[dict[str, Any]] = []
        queries = self.cfg.get("news_queries", [])
        newsapi = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
        newsdata = os.getenv("NEWS_DATA_IO_KEY") or os.getenv("NEWSDATA_IO_KEY") or os.getenv("NEWSDATA_KEY")
        gdelt_base = self.cfg.get("apis", {}).get("gdelt_doc_api", "https://api.gdeltproject.org/api/v2/doc/doc")
        since = (utc_now() - timedelta(days=self.lookback_days)).strftime("%Y%m%d%H%M%S")
        for q in queries:
            if newsapi:
                url = "https://newsapi.org/v2/everything?" + urllib.parse.urlencode({"q": q, "language": "en", "sortBy": "publishedAt", "pageSize": 50, "from": (utc_now()-timedelta(days=self.lookback_days)).date().isoformat(), "apiKey": newsapi})
                data, rec = self.request_json("NewsAPI everything", "news_api", url, query=q)
                out = self.news_dir / "raw" / f"newsapi_{safe_name(q)}_{self.ts}.json"
                self.save_response(rec, data, out, count=len((data or {}).get("articles", [])) if isinstance(data, dict) else 0)
                for a in (data or {}).get("articles", []) if isinstance(data, dict) else []:
                    a["aq26_source"] = "NewsAPI"; a["aq26_query"] = q; articles.append(a)
            if newsdata:
                url = "https://newsdata.io/api/1/news?" + urllib.parse.urlencode({"apikey": newsdata, "q": q, "language": "en", "size": 10})
                data, rec = self.request_json("NewsData.io news", "news_api", url, query=q)
                out = self.news_dir / "raw" / f"newsdata_{safe_name(q)}_{self.ts}.json"
                results = (data or {}).get("results", []) if isinstance(data, dict) else []
                self.save_response(rec, data, out, count=len(results))
                for a in results:
                    a["aq26_source"] = "NewsData.io"; a["aq26_query"] = q; articles.append(a)
            gdelt_url = gdelt_base + "?" + urllib.parse.urlencode({"query": q, "mode": "ArtList", "format": "json", "maxrecords": 50, "sort": "HybridRel", "startdatetime": since})
            data, rec = self.request_json("GDELT document API", "news_api", gdelt_url, query=q)
            out = self.news_dir / "raw" / f"gdelt_{safe_name(q)}_{self.ts}.json"
            gd_articles = (data or {}).get("articles", []) if isinstance(data, dict) else []
            self.save_response(rec, data, out, count=len(gd_articles))
            for a in gd_articles:
                a["aq26_source"] = "GDELT"; a["aq26_query"] = q; articles.append(a)
        keep_terms = {t.lower() for q in (self.cfg.get("news_queries", []) + self.cfg.get("official_queries", [])) for t in re.findall(r"[A-Za-z0-9-]{4,}", q)}
        for a in articles:
            text = json.dumps(a, ensure_ascii=False).lower()
            score = sum(1 for t in keep_terms if t in text)
            if score > 0:
                b = dict(a); b["aq26_relevance_score"] = score; kept.append(b)
        self.write_json(self.news_dir / "news_articles.json", {"run_ts": self.ts, "lookback_days": self.lookback_days, "articles": articles})
        self.write_json(self.news_dir / "news_kept_articles.json", {"run_ts": self.ts, "articles": kept})

    def harvest_weather_and_ground(self) -> None:
        sites = self.cfg.get("sites", [])
        openweather = os.getenv("OPENWEATHER_KEY") or os.getenv("OPENWEATHER_API_KEY")
        waqi = os.getenv("WAQI_TOKEN")
        met_url = os.getenv("MET_OFFICE_LAND_OBSERVATIONS") or os.getenv("METOFFICE_LAND_OBSERVATIONS")
        met_key = os.getenv("METOFFICE_API_KEY") or os.getenv("MET_OFFICE_KEY")
        openaq_key = os.getenv("OPENAQ_API_KEY")
        openaq_base = self.cfg.get("apis", {}).get("openaq_v3_base", "https://api.openaq.org/v3")
        for site in sites:
            sid = site.get("site_id", "SITE")
            lat = site.get("lat"); lon = site.get("lon")
            if lat is None or lon is None:
                continue
            if openweather:
                for endpoint, params, stype in [
                    ("weather", {"lat": lat, "lon": lon, "appid": openweather, "units": "metric"}, "weather_current"),
                    ("forecast", {"lat": lat, "lon": lon, "appid": openweather, "units": "metric"}, "weather_forecast"),
                    ("air_pollution", {"lat": lat, "lon": lon, "appid": openweather}, "ground_air_quality"),
                ]:
                    url = f"{self.cfg.get('apis', {}).get('openweather_base', 'https://api.openweathermap.org/data/2.5')}/{endpoint}?" + urllib.parse.urlencode(params)
                    data, rec = self.request_json(f"OpenWeather {endpoint}", stype, url, query=sid)
                    out = self.weather_dir / f"openweather_{endpoint}_{sid}_{self.ts}.json" if endpoint != "air_pollution" else self.ground_dir / f"openweather_air_pollution_{sid}_{self.ts}.json"
                    self.save_response(rec, data, out)
            if waqi:
                url = f"{self.cfg.get('apis', {}).get('waqi_geo_base', 'https://api.waqi.info/feed/geo:')}{lat};{lon}/?" + urllib.parse.urlencode({"token": waqi})
                data, rec = self.request_json("WAQI geo feed", "ground_air_quality", url, query=sid)
                self.save_response(rec, data, self.ground_dir / f"waqi_geo_{sid}_{self.ts}.json")
            headers = {}
            if openaq_key:
                headers["X-API-Key"] = openaq_key
            loc_url = f"{openaq_base}/locations?" + urllib.parse.urlencode({"coordinates": f"{lat},{lon}", "radius": int(site.get("radius_m", 25000)), "limit": 100})
            data, rec = self.request_json("OpenAQ v3 nearby locations", "ground_air_quality_metadata", loc_url, query=sid, headers=headers)
            self.save_response(rec, data, self.ground_dir / f"openaq_locations_{sid}_{self.ts}.json", count=len((data or {}).get("results", [])) if isinstance(data, dict) else 0)
            latest_url = f"{openaq_base}/latest?" + urllib.parse.urlencode({"coordinates": f"{lat},{lon}", "radius": int(site.get("radius_m", 25000)), "limit": 100})
            data, rec = self.request_json("OpenAQ v3 latest", "ground_air_quality", latest_url, query=sid, headers=headers)
            self.save_response(rec, data, self.ground_dir / f"openaq_latest_{sid}_{self.ts}.json", count=len((data or {}).get("results", [])) if isinstance(data, dict) else 0)
            if met_url:
                sep = "&" if "?" in met_url else "?"
                url = met_url + sep + urllib.parse.urlencode({"lat": lat, "lon": lon})
                headers = {"apikey": met_key} if met_key else {}
                data, rec = self.request_json("Met Office configured observations endpoint", "weather_observations", url, query=sid, headers=headers)
                self.save_response(rec, data, self.weather_dir / f"metoffice_configured_observations_{sid}_{self.ts}.json")
        # compatibility summary file expected by existing notebooks
        summary = {"run_ts": self.ts, "weather_ready": any(r.source_type.startswith("weather") and r.status == "ok" for r in self.records), "records": [asdict(r) for r in self.records if r.source_type.startswith("weather")]}
        self.write_json(self.weather_dir / "weather_current_and_forecast.json", summary)

    def extract_links(self, text: str, base_url: str) -> list[str]:
        links = []
        for m in re.finditer(r'href=["\']([^"\']+)["\']', text, flags=re.I):
            href = html.unescape(m.group(1))
            links.append(urllib.parse.urljoin(base_url, href))
        return sorted(set(links))

    def download_file(self, url: str, label: str, max_mb: int) -> dict[str, Any]:
        out = {"url": url, "status": "not_started"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=45) as resp:
                size = int(resp.headers.get("content-length") or 0)
                if size and size > max_mb * 1024 * 1024:
                    out.update({"status": "skipped_too_large", "bytes": size}); return out
                raw = resp.read(max_mb * 1024 * 1024 + 1)
                if len(raw) > max_mb * 1024 * 1024:
                    out.update({"status": "skipped_too_large", "bytes": len(raw)}); return out
            suffix = Path(urllib.parse.urlparse(url).path).suffix or ".bin"
            path = self.download_dir / f"{safe_name(label)}_{sha256_bytes(url.encode())[:10]}{suffix}"
            path.write_bytes(raw)
            out.update({"status": "downloaded", "path": str(path), "bytes": len(raw), "sha256": sha256_file(path)})
        except Exception as e:
            out.update({"status": "error", "error": repr(e)})
        return out

    def harvest_official_filings(self) -> None:
        filings: list[dict[str, Any]] = []
        official_queries = self.cfg.get("official_queries", [])
        govuk_api = self.cfg.get("apis", {}).get("govuk_search_api", "https://www.gov.uk/api/search.json")
        dgu_api = self.cfg.get("apis", {}).get("datagovuk_package_search", "https://www.data.gov.uk/api/3/action/package_search")
        for q in official_queries:
            gov_url = govuk_api + "?" + urllib.parse.urlencode({"q": q, "count": 50})
            data, rec = self.request_json("GOV.UK search", "official_search", gov_url, query=q)
            self.save_response(rec, data, self.official_dir / "raw" / f"govuk_search_{safe_name(q)}_{self.ts}.json", count=len((data or {}).get("results", [])) if isinstance(data, dict) else 0)
            for item in (data or {}).get("results", []) if isinstance(data, dict) else []:
                filings.append({"source": "GOV.UK", "query": q, "title": item.get("title"), "url": urllib.parse.urljoin("https://www.gov.uk", item.get("link", "")), "raw": item})
            dgu_url = dgu_api + "?" + urllib.parse.urlencode({"q": q, "rows": 50})
            data, rec = self.request_json("data.gov.uk CKAN package_search", "official_dataset_search", dgu_url, query=q)
            count = ((data or {}).get("result", {}) or {}).get("count", 0) if isinstance(data, dict) else 0
            self.save_response(rec, data, self.official_dir / "raw" / f"datagovuk_search_{safe_name(q)}_{self.ts}.json", count=count)
            for pkg in (((data or {}).get("result", {}) or {}).get("results", []) if isinstance(data, dict) else []):
                filings.append({"source": "data.gov.uk", "query": q, "title": pkg.get("title") or pkg.get("name"), "url": pkg.get("url") or f"https://www.data.gov.uk/dataset/{pkg.get('name','')}", "resources": pkg.get("resources", []), "raw": pkg})
        for w in self.cfg.get("official_watchlist_urls", []):
            url = w.get("url")
            if not url: continue
            data, rec = self.request_json(w.get("label", "official watchlist URL"), w.get("source_type", "official_watchlist"), url, query=w.get("label", ""))
            self.save_response(rec, data, self.official_dir / "raw" / f"watchlist_{safe_name(w.get('label','url'))}_{self.ts}.json")
            text = (data or {}).get("raw_text", "") if isinstance(data, dict) else ""
            links = self.extract_links(text, url)[:200]
            filings.append({"source": w.get("label"), "query": "watchlist", "title": w.get("label"), "url": url, "links": links, "raw": {"watchlist": w}})
        downloads = []
        if self.download_official_files:
            file_re = re.compile(r"\.(pdf|xlsx?|csv|docx?|ods)(\?|$)", re.I)
            candidate_urls = []
            for f in filings:
                for r in f.get("resources", []) or []:
                    if r.get("url"): candidate_urls.append((r.get("url"), f.get("title") or "resource"))
                for link in f.get("links", []) or []:
                    if file_re.search(link): candidate_urls.append((link, f.get("title") or "link"))
            seen = set()
            for url, label in candidate_urls[:80]:
                if url in seen: continue
                seen.add(url)
                downloads.append(self.download_file(url, label, int(self.cfg.get("max_download_mb", 20))))
        self.write_json(self.official_dir / "official_filing_index.json", {"run_ts": self.ts, "lookback_days": self.lookback_days, "filing_count": len(filings), "filings": filings, "downloads": downloads})
        # best-effort changed-source index: stable hash of URLs/titles for comparison in downstream reports
        changed = []
        for f in filings:
            key = sha256_bytes(json.dumps({"title": f.get("title"), "url": f.get("url"), "source": f.get("source")}, sort_keys=True).encode())
            changed.append({"change_status": "seen_this_run", "fingerprint": key, "title": f.get("title"), "url": f.get("url"), "source": f.get("source"), "query": f.get("query")})
        self.write_json(self.official_dir / "new_or_changed_source_index.json", {"run_ts": self.ts, "items": changed})

    def harvest_satellite_metadata(self) -> None:
        sites = self.cfg.get("sites", [])
        stac_url = self.cfg.get("apis", {}).get("copernicus_stac_search", "https://catalogue.dataspace.copernicus.eu/stac/search")
        start = (utc_now() - timedelta(days=self.lookback_days)).date().isoformat() + "T00:00:00Z"
        end = utc_now().date().isoformat() + "T23:59:59Z"
        for site in sites:
            sid = site.get("site_id", "SITE")
            lat = float(site.get("lat")); lon = float(site.get("lon"))
            delta = 0.35
            body = json.dumps({
                "collections": ["SENTINEL-5P", "SENTINEL-2"],
                "bbox": [lon-delta, lat-delta, lon+delta, lat+delta],
                "datetime": f"{start}/{end}",
                "limit": 100,
            }).encode("utf-8")
            data, rec = self.request_json("Copernicus Data Space STAC search", "satellite_metadata", stac_url, query=sid, method="POST", body=body, headers={"Content-Type": "application/json"})
            features = (data or {}).get("features", []) if isinstance(data, dict) else []
            self.save_response(rec, data, self.sat_dir / f"copernicus_stac_{sid}_{self.ts}.json", count=len(features))
        # compatibility summary for satellite layer
        sat_records = [asdict(r) for r in self.records if r.source_type == "satellite_metadata"]
        self.write_json(self.sat_dir / "satellite_catalogue_metadata.json", {"run_ts": self.ts, "records": sat_records})

    def write_manifests(self) -> None:
        source_records = [asdict(r) for r in self.records]
        csv_path = self.harvest_root / f"AQ26_LIVE_SOURCE_RECORDS_{self.ts}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            fields = list(source_records[0].keys()) if source_records else ["run_ts"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader(); w.writerows(source_records)
        manifest = {
            "run_ts": self.ts,
            "project": self.cfg.get("project_name", "SCCNEXUS AirQuality26"),
            "controlled_use_boundary": self.cfg.get("controlled_use_boundary", "controlled review only"),
            "lookback_days": self.lookback_days,
            "output_root": str(self.output_root),
            "harvest_root": str(self.harvest_root),
            "source_record_count": len(source_records),
            "ok_count": sum(1 for r in self.records if r.status == "ok"),
            "error_count": sum(1 for r in self.records if r.status == "error"),
            "secrets_status": redacted_env_status(["OPENWEATHER_KEY", "OPENWEATHER_API_KEY", "WAQI_TOKEN", "NEWS_API_KEY", "NEWSAPI_KEY", "NEWS_DATA_IO_KEY", "NEWSDATA_IO_KEY", "METOFFICE_API_KEY", "MET_OFFICE_KEY", "MET_OFFICE_LAND_OBSERVATIONS", "CDSE_USERNAME", "CDSE_PASSWORD", "OPENAQ_API_KEY"]),
            "source_records_csv": str(csv_path),
            "source_records": source_records,
        }
        manifest_path = self.harvest_root / f"AQ26_LIVE_HARVEST_MANIFEST_{self.ts}.json"
        self.write_json(manifest_path, manifest)
        latest = self.output_root / "00_live_harvest" / "LATEST_HARVEST.json"
        self.write_json(latest, manifest)
        # append jsonl history for provenance within the repository workspace/artifact
        hist = self.history_dir / "source_index.jsonl"
        with hist.open("a", encoding="utf-8") as f:
            for rec in source_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps({"harvest_root": str(self.harvest_root), "manifest": str(manifest_path), "source_record_count": len(source_records), "ok_count": manifest["ok_count"], "error_count": manifest["error_count"]}, indent=2))

    def run(self) -> None:
        self.harvest_news()
        self.harvest_weather_and_ground()
        self.harvest_official_filings()
        self.harvest_satellite_metadata()
        self.write_manifests()


def main() -> int:
    ap = argparse.ArgumentParser(description="AQ26 GitHub-only live/current evidence preflight harvester")
    ap.add_argument("--config", default="configs/aq26_live_harvest.yml")
    ap.add_argument("--output-root", default="outputs")
    ap.add_argument("--lookback-days", type=int, default=None)
    ap.add_argument("--download-official-files", default="true")
    args = ap.parse_args()
    cfg = read_yaml(Path(args.config))
    lookback = args.lookback_days or int(cfg.get("lookback_days_default", 14))
    download = str(args.download_official_files).lower() in {"1", "true", "yes", "y"}
    Harvester(cfg, Path(args.output_root), lookback, download).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
