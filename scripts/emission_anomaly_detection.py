
import pandas as pd

df = pd.read_parquet("warehouse/pollution_inventory_master.parquet")

df["quantity"] = pd.to_numeric(df.get("quantity"), errors="coerce")

site_pollutant = (
    df.groupby(["site_name", "pollutant", "report_year"])["quantity"]
    .sum()
    .reset_index()
)

site_pollutant["year_change"] = (
    site_pollutant.groupby(["site_name","pollutant"])["quantity"].pct_change()
)

outliers = site_pollutant[site_pollutant["year_change"].abs() > 0.5]

Path("outputs").mkdir(exist_ok=True)

outliers.to_csv(
    "outputs/emission_anomaly_candidates.csv",
    index=False
)

print("Anomaly detection complete.")
