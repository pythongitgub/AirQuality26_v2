
import requests
import zipfile
import io
import yaml
from pathlib import Path

CONFIG = yaml.safe_load(open("configs/pollution_inventory.yml"))

OUT_DIR = Path("datasets/pollution_inventory")
OUT_DIR.mkdir(parents=True, exist_ok=True)

for year, url in CONFIG["download_urls"].items():
    print(f"Downloading Pollution Inventory {year}")
    r = requests.get(url, timeout=120)

    if r.status_code != 200:
        print("Download failed:", url)
        continue

    z = zipfile.ZipFile(io.BytesIO(r.content))

    year_dir = OUT_DIR / str(year)
    year_dir.mkdir(exist_ok=True)

    z.extractall(year_dir)

print("Download complete.")
