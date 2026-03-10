from pathlib import Path
import pandas as pd

DATA_DIR = Path("datasets/pollution_inventory")
OUT_DIR = Path("warehouse")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {path}")

files = []
for pattern in ["**/*.csv", "**/*.xlsx", "**/*.xls"]:
    files.extend(DATA_DIR.glob(pattern))

files = [f for f in files if f.is_file() and not f.name.startswith("~$")]

print(f"Found {len(files)} candidate files")

if not files:
    raise RuntimeError(
        "No Pollution Inventory tabular files found after download/extract. "
        "Check ZIP contents and extraction paths."
    )

frames = []

for f in files:
    try:
        print("Reading", f)
        df = read_table(f)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # infer year from parent folders or filename
        year = None
        for part in f.parts:
            if str(part).isdigit() and len(str(part)) == 4:
                year = int(part)
                break
        if year is None:
            for y in range(2016, 2025):
                if str(y) in f.name:
                    year = y
                    break

        df["report_year"] = year
        df["source_file"] = str(f)
        frames.append(df)

    except Exception as e:
        print(f"WARNING: failed to read {f}: {e}")

if not frames:
    raise RuntimeError(
        "Files were found, but none could be parsed into tables. "
        "Likely schema/format issue."
    )

master = pd.concat(frames, ignore_index=True, sort=False)
master.to_parquet("warehouse/pollution_inventory_master.parquet", index=False)

print("Warehouse written:", len(master), "rows")
