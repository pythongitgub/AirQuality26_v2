import os
import requests
from datetime import datetime, timezone

def env(name: str) -> str:
    v = os.getenv(name, "")
    return v.strip() if isinstance(v, str) else ""

def ok(msg): print(f"✅ {msg}")
def warn(msg): print(f"⚠️ {msg}")
def fail(msg): raise RuntimeError(msg)

print("UTC now:", datetime.now(timezone.utc).isoformat())

# --- Presence check (everything you listed) ---
ALL_SECRETS = [
    "CDSE_USERNAME", "CDSE_PASSWORD",
    "CDSE_ID", "CDSE_SECRET",
    "OPENWEATHER_KEY",
    "WAQI_TOKEN",
    "AIRQUALITY",
    "NEWS_API_KEY",
    "NEWS_DATA_IO_KEY",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MET_OFFICE_KEY",          # optional naming    
    "MET_OFFICE_LAND_OBSERVATIONS",
]

present = {k: bool(env(k)) for k in ALL_SECRETS}
missing = [k for k,v in present.items() if not v]
print("Secrets present:", sum(present.values()), "/", len(ALL_SECRETS))
if missing:
    warn(f"Missing (may be optional): {missing}")

# -------------------------
# 1) CDSE password token
# -------------------------
if env("CDSE_USERNAME") and env("CDSE_PASSWORD"):
    r = requests.post(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": env("CDSE_USERNAME"),
            "password": env("CDSE_PASSWORD"),
        },
        timeout=30,
    )
    if r.ok and "access_token" in r.json():
        ok("CDSE password token OK")
    else:
        warn(f"CDSE password auth failed (HTTP {r.status_code})")
else:
    warn("CDSE_USERNAME/CDSE_PASSWORD not set; skipping password token test")

# -------------------------
# 2) Sentinel Hub client credentials (CDSE_ID/CDSE_SECRET)
# -------------------------
if env("CDSE_ID") and env("CDSE_SECRET"):
    r = requests.post(
        "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": env("CDSE_ID"),
            "client_secret": env("CDSE_SECRET"),
        },
        timeout=30,
    )
    if r.ok and "access_token" in r.json():
        ok("Sentinel Hub client-credentials token OK (CDSE_ID/CDSE_SECRET)")
    else:
        warn(f"Sentinel Hub client-credentials failed (HTTP {r.status_code})")
else:
    warn("CDSE_ID/CDSE_SECRET not set; skipping client-credentials test")

# -------------------------
# 3) OpenWeather
# -------------------------
if env("OPENWEATHER_KEY"):
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"lat": 51.5, "lon": 0.0, "appid": env("OPENWEATHER_KEY")},
        timeout=30,
    )
    ok("OpenWeather OK") if r.ok else warn(f"OpenWeather failed (HTTP {r.status_code})")
else:
    warn("OPENWEATHER_KEY not set; skipping")

# -------------------------
# 4) WAQI
# -------------------------
if env("WAQI_TOKEN"):
    r = requests.get(
        "https://api.waqi.info/feed/geo:51.5074;0.1278/",
        params={"token": env("WAQI_TOKEN")},
        timeout=30,
    )
    ok("WAQI OK") if (r.ok and r.json().get("status") == "ok") else warn("WAQI failed")
else:
    warn("WAQI_TOKEN not set; skipping")

# -------------------------
# 5) NewsAPI.org
# -------------------------
if env("NEWS_API_KEY"):
    r = requests.get(
        "https://newsapi.org/v2/everything",
        params={"q": "air quality UK", "pageSize": 1, "sortBy": "publishedAt"},
        headers={"X-Api-Key": env("NEWS_API_KEY")},
        timeout=30,
    )
    ok("NewsAPI OK") if r.ok else warn(f"NewsAPI failed (HTTP {r.status_code})")
else:
    warn("NEWS_API_KEY not set; skipping")

# -------------------------
# 6) NewsData.io
# -------------------------
if env("NEWS_DATA_IO_KEY"):
    r = requests.get(
        "https://newsdata.io/api/1/news",
        params={"apikey": env("NEWS_DATA_IO_KEY"), "q": "air quality UK", "language": "en", "size": 1},
        timeout=30,
    )
    ok("NewsData.io OK") if r.ok else warn(f"NewsData.io failed (HTTP {r.status_code})")
else:
    warn("NEWS_DATA_IO_KEY not set; skipping")

# -------------------------
# 7) Gemini (API key) — verifies key by listing models (light call)
# -------------------------
# Note: Gemini endpoints may require a different base URL depending on your setup.
# This call attempts the common Google Generative Language API endpoint.
if env("GEMINI_API_KEY"):
    r = requests.get(
        "https://generativelanguage.googleapis.com/v1/models",
        params={"key": env("GEMINI_API_KEY")},
        timeout=30,
    )
    ok("Gemini API key OK (models list)") if r.ok else warn(f"Gemini failed (HTTP {r.status_code})")
    if env("GEMINI_MODEL"):
        ok(f"GEMINI_MODEL set to '{env('GEMINI_MODEL')}'")
    else:
        warn("GEMINI_MODEL not set (optional)")
else:
    warn("GEMINI_API_KEY not set; skipping")

# -------------------------
# 8) Met Office (optional) — just checks presence + tries a simple endpoint if you tell me which product you use
# -------------------------
met_key = env("MET_OFFICE_KEY") or env("METOFFICE_API_KEY")
if met_key:
    ok("Met Office key present (not fully validated: endpoint depends on your Met Office product)")
else:
    warn("No Met Office key present; skipping")

# -------------------------
# 9) AIRQUALITY (unknown provider) — presence only until we know the API
# -------------------------
if env("AIRQUALITY"):
    ok("AIRQUALITY secret present (not validated: need provider/endpoint)")
else:
    warn("AIRQUALITY not set; skipping")

# -------------------------
# 10) IQAir (AirVisual) API Test
# -------------------------
if env("IQ_AIR_QUALITY_KEY"):
    r = requests.get(
        "https://api.airvisual.com/v2/nearest_city",
        params={
            "lat": 51.5074,
            "lon": -0.1278,
            "key": env("IQ_AIR_QUALITY_KEY"),
        },
        timeout=30,
    )
    if r.ok and r.json().get("status") == "success":
        ok("IQAir API OK")
    else:
        warn(f"IQAir failed (HTTP {r.status_code})")
else:
    warn("IQ_AIR_QUALITY_KEY not set; skipping")

# -------------------------
#11) Ambee Air Quality test
# -------------------------
if env("GETAMBEE_AIR_QUALITY_KEY"):
    r = requests.get(
        "https://api.ambeedata.com/latest/by-lat-lng",
        params={"lat": 50.873, "lng": 0.008},  # Lewes-ish
        headers={"x-api-key": env("GETAMBEE_AIR_QUALITY_KEY")},
        timeout=30,
    )
    if r.ok:
        ok("Ambee API OK")
    else:
        warn(f"Ambee failed (HTTP {r.status_code})")
else:
    warn("GETAMBEE_AIR_QUALITY_KEY not set; skipping")

print("Smoke test complete.")
