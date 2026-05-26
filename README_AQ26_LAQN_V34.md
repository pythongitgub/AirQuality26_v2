# AQ26 LAQN Provider V3.4

This patch adds a first-stage London Air Quality Network / Imperial ERG AirQuality API provider probe.

Provider help page:
`https://api.erg.ic.ac.uk/AirQuality/help`

## Files

```text
configs/aq26_laqn.yml
scripts/aq26_provider_laqn.py
.github/workflows/aq26_laqn_probe.yml
requirements-laqn.txt
docs/laqn_provider_v34_notes.md
```

## What it does

The workflow fetches LAQN metadata:

```text
/Information/Species/Json
/Information/Groups/Json
/Information/MonitoringSites/GroupName=London/Json
/Information/MonitoringSiteSpecies/GroupName=London/Json
/Information/IndexHealthAdvice/Json
```

Optionally, it runs a tiny one-site/one-species historical data probe:

```text
/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json
```

## Recommended first run

```text
Actions → AQ26 LAQN Provider Probe V3.4 → Run workflow
```

Use:

```text
group_name: London
run_data_probe: false
commit_outputs: true
```

## Recommended second run

After the metadata run passes:

```text
run_data_probe: true
probe_site_code: leave blank
probe_species_code: leave blank
observation_start_date: 2024-07-22
observation_end_date: 2024-07-23
```

The script will try to auto-select the first site/species pair from LAQN site/species metadata.

## Scientific caveat

LAQN is a validated London/urban comparator provider. It is useful for control/context evidence and pollutant metadata. It must not be presented as Newhaven-specific evidence unless it is explicitly used as an urban/control comparator.

## Outputs

```text
outputs/31_laqn/laqn_source_records.json
outputs/31_laqn/laqn_source_records.csv
outputs/31_laqn/laqn_summary.json
site_public/data/providers/laqn/species.json
site_public/data/providers/laqn/groups.json
site_public/data/providers/laqn/sites_london.json
site_public/data/providers/laqn/site_species_london.json
site_public/data/providers/laqn/index_health_advice.json
site_public/data/providers/laqn/source_records.json
site_public/data/providers/laqn/summary.json
```

## Later integration

Once the probe passes, import `outputs/31_laqn/laqn_source_records.json` into the AQ26 science backfill source-record ledger, and use the tiny data probe to determine the stable observation schema before bulk LAQN harvesting.
