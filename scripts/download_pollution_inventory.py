import requests
import zipfile
import io
import yaml
from pathlib import Path

CONFIG = yaml.safe_load(open("configs/pollution_inventory.yml"))

OUT_DIR = Path("datasets/pollution_inventory")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AQ26 Environmental Analysis"
}

for year, url in CONFIG["download_urls"].items():

    print(f"Downloading {year}")

    r = requests.get(url, headers=HEADERS, timeout=300)

    if r.status_code != 200:
        print("Failed:", r.status_code)
        continue

    try:

        z = zipfile.ZipFile(io.BytesIO(r.content))

    except zipfile.BadZipFile:

        print("Not a zip file:", year)
        continue

    year_dir = OUT_DIR / str(year)
    year_dir.mkdir(exist_ok=True)

    z.extractall(year_dir)

    print("Extracted:", year)

print("Download stage complete.")
