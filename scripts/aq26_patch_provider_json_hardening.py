#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

PIPELINE = Path("scripts/aq26_production_pipeline.py")

NEW_HTTP_GET_JSON = """def http_get_json(ctx: Context, source_name: str, source_type: str, url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]], output_path: Path, timeout: int = 30) -> Dict[str, Any]:
    \\\"\\\"\\\"Fetch a provider JSON endpoint without ever writing invalid JSON to *.json.

    Some upstream providers occasionally return HTML, empty bodies, rate-limit
    messages, or maintenance text while still using a URL that normally returns
    JSON. The AQ26 validation gate is correct to reject invalid *.json files, so
    this helper now stores the raw non-JSON payload as *.raw.txt and writes a
    valid warning JSON envelope at the requested *.json path.
    \\\"\\\"\\\"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
        redacted_url = redact_text(resp.url)
        payload_text = redact_text(resp.text[:2_000_000])
        content_type = resp.headers.get("content-type", "")

        count = ""
        try:
            data = json.loads(payload_text)
            write_json(output_path, data)
            if isinstance(data, dict):
                if isinstance(data.get("results"), list):
                    count = len(data["results"])
                elif isinstance(data.get("data"), list):
                    count = len(data["data"])
                elif "meta" in data:
                    count = data.get("meta", {}).get("found", "")
            return make_source_record(
                ctx,
                source_name=source_name,
                source_type=source_type,
                url=redacted_url,
                query=json.dumps(params),
                status="ok" if resp.ok else "warning",
                http_status=resp.status_code,
                output_path=str(output_path),
                record_count=count,
                error="" if resp.ok else payload_text[:300],
            )
        except Exception as json_exc:
            raw_path = output_path.with_suffix(".raw.txt")
            raw_path.write_text(payload_text, encoding="utf-8")
            warning_doc = {
                "generated_at_utc": ctx.run_dt_utc.isoformat(),
                "source_name": source_name,
                "source_type": source_type,
                "status": "warning",
                "warning_type": "non_json_provider_response",
                "http_status": resp.status_code,
                "content_type": content_type,
                "url_redacted": redacted_url,
                "query": params,
                "raw_payload_path": str(raw_path),
                "raw_payload_bytes": raw_path.stat().st_size if raw_path.exists() else 0,
                "json_error": f"{type(json_exc).__name__}: {json_exc}",
                "raw_payload_preview": payload_text[:1000],
                "note": "Provider probe did not return parseable JSON. Raw payload is preserved as .raw.txt; this JSON envelope keeps AQ26 validation deterministic.",
            }
            write_json(output_path, warning_doc)
            return make_source_record(
                ctx,
                source_name=source_name,
                source_type=source_type,
                url=redacted_url,
                query=json.dumps(params),
                status="warning",
                http_status=resp.status_code,
                output_path=str(output_path),
                record_count=0,
                error=f"Non-JSON provider response: {type(json_exc).__name__}: {json_exc}",
                notes=f"Raw payload saved to {raw_path}",
            )
    except Exception as e:
        error_doc = {
            "generated_at_utc": ctx.run_dt_utc.isoformat(),
            "source_name": source_name,
            "source_type": source_type,
            "status": "warning",
            "warning_type": "provider_request_exception",
            "url_redacted": redact_text(url),
            "query": params,
            "error": redact_text(str(e)),
            "note": "Provider request failed before a parseable response was received. This valid JSON envelope prevents invalid-provider output from breaking the whole weekly publication.",
        }
        write_json(output_path, error_doc)
        return make_source_record(
            ctx,
            source_name=source_name,
            source_type=source_type,
            url=url,
            query=json.dumps(params),
            status="warning",
            http_status="",
            output_path=str(output_path),
            record_count=0,
            error=str(e),
        )


"""

def main() -> int:
    if not PIPELINE.exists():
        print(f"ERROR: {PIPELINE} not found. Run this from the AirQuality26_v2 repo root.", file=sys.stderr)
        return 1

    text = PIPELINE.read_text(encoding="utf-8")
    if "warning_type\": \"non_json_provider_response\"" in text or "warning_type': 'non_json_provider_response'" in text:
        print("Provider JSON hardening already appears to be installed.")
        return 0

    pattern = re.compile(
        r"def http_get_json\(ctx: Context, source_name: str, source_type: str, url: str, params: Dict\[str, Any\], headers: Optional\[Dict\[str, str\]\], output_path: Path, timeout: int = 30\) -> Dict\[str, Any\]:\n.*?\n\n(?=def copy_branding\(ctx: Context\) -> None:)",
        re.DOTALL,
    )
    new_text, count = pattern.subn(NEW_HTTP_GET_JSON, text)
    if count != 1:
        print("ERROR: Could not safely locate exactly one http_get_json function to replace.", file=sys.stderr)
        print("No changes made.", file=sys.stderr)
        return 2

    backup = PIPELINE.with_suffix(".py.bak_provider_json_hardening")
    backup.write_text(text, encoding="utf-8")
    PIPELINE.write_text(new_text, encoding="utf-8")
    print(f"Patched {PIPELINE}")
    print(f"Backup written to {backup}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
