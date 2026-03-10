
import pandas as pd

fusion = pd.read_csv("outputs/site_geospatial_fusion.csv")
anomalies = pd.read_csv("outputs/emission_anomaly_candidates.csv")

targets = fusion[fusion["site_key"].isin(anomalies["site_name"])]
controls = fusion.sample(min(5, len(fusion)))

targets["group"] = "target"
controls["group"] = "control"

investigation = pd.concat([targets, controls])

investigation.to_csv(
    "outputs/investigation_sites.csv",
    index=False
)

print("Investigation sites selected.")
