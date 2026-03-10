import requests
import zipfile
import io
import yaml
from pathlib import Path

CONFIG = yaml.safe_load(open("configs/pollution_inventory.yml"))

OUT_DIR = Path("datasets/pollution_inventory")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "AQ26 Environmental Analysis"}

for year, url in CONFIG["download_urls"].items():
    print(f"Downloading {year}")
    r = requests.get(url, headers=HEADERS, timeout=300)

    if r.status_code != 200:
        print(f"Failed {year}: HTTP {r.status_code}")
        continue

    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        print(f"Failed {year}: response was not a valid ZIP")
        continue

    year_dir = OUT_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    names = z.namelist()
    print(f"{year}: ZIP contains {len(names)} files")
    for n in names[:20]:
        print(" -", n)

    z.extractall(year_dir)
    print(f"Extracted {year} to {year_dir}")

print("Download stage complete.")
