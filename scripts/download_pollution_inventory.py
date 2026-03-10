import requests
import zipfile
import io
import yaml
from pathlib import Path

CONFIG = yaml.safe_load(open("configs/pollution_inventory.yml"))

OUT_DIR = Path("datasets/pollution_inventory")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AQ26 Environmental Analysis Bot"
}

for year, url in CONFIG["download_urls"].items():

    print(f"Downloading Pollution Inventory {year}")

    r = requests.get(url, headers=HEADERS, timeout=120)

    if r.status_code != 200:
        print(f"Download failed ({r.status_code}) :", url)
        continue

    content_type = r.headers.get("content-type","")

    # detect HTML page instead of zip
    if "html" in content_type.lower():
        print("WARNING: URL returned HTML instead of ZIP")
        print("Likely incorrect dataset link:", url)
        continue

    try:

        z = zipfile.ZipFile(io.BytesIO(r.content))

    except zipfile.BadZipFile:

        print("WARNING: Not a valid ZIP file:", url)
        continue

    year_dir = OUT_DIR / str(year)
    year_dir.mkdir(exist_ok=True)

    z.extractall(year_dir)

    print(f"Extracted {year}")

print("Download stage complete.")
