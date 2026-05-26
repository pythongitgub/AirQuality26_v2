# AQ26 LAQN Provider V3.4 Notes

The LAQN / Imperial ERG API help page confirms these high-value endpoints:

- `/Information/Species/Json` — pollutant/species code metadata and health-effect descriptions.
- `/Information/MonitoringSites/GroupName={GroupName}/Json` — monitoring sites for a group, currently including `London`.
- `/Information/MonitoringSiteSpecies/GroupName={GroupName}/Json` — site/species availability for a group.
- `/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json` — raw data by site, pollutant and date range.
- `/Data/Wide/Site/SiteCode={SiteCode}/StartDate={StartDate}/EndDate={EndDate}/Json` — raw wide-format data by site and date range.

AQ26 usage policy:
- Treat LAQN as a validated urban comparator and pollutant metadata provider.
- Label LAQN data as `historical_observation` only when the `/Data/...` endpoint is used for an explicit date range.
- Label metadata endpoints as `reference_metadata`.
- Do not treat LAQN as direct evidence about Newhaven unless explicitly framed as comparator/control context.
