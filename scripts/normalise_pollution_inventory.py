
import pandas as pd
from pathlib import Path

DATA_DIR = Path("datasets/pollution_inventory")
frames = []

for year_dir in DATA_DIR.iterdir():
    for f in year_dir.glob("*.csv"):
        print("Reading", f)
        df = pd.read_csv(f)
        df.columns = [c.lower().strip() for c in df.columns]
        df["report_year"] = year_dir.name
        frames.append(df)

master = pd.concat(frames, ignore_index=True)

Path("warehouse").mkdir(exist_ok=True)

master.to_parquet(
    "warehouse/pollution_inventory_master.parquet",
    index=False
)

print("Warehouse written.")
