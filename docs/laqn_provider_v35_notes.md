# AQ26 LAQN v3.5 + NASA Earthdata CMR repository patch

## Why this patch exists

Your attached repository already contains the LAQN v3.4 provider and the committed `outputs/31_laqn` run. The workflow itself passed, but the output is currently a metadata-only LAQN success, not an observation-data success.

The chart issue is not caused by "empty London Air" overall. It is caused by front-end unsafe provider output:
- empty `WebsiteURL` fields are valid in the LAQN group metadata;
- the annual objective endpoint returns XML, not JSON;
- LAQN uses XML-style JSON keys such as `@SiteCode`;
- the site should not chart raw provider payloads directly;
- v3.4 writes absolute GitHub runner paths into some source records.

## Files changed

- `scripts/aq26_provider_laqn.py`
- `configs/aq26_laqn.yml`
- `.github/workflows/aq26_laqn_probe.yml`
- `site_public/assets/aq26_charts_v3.js`
- `scripts/aq26_provider_earthdata.py`
- `configs/aq26_earthdata.yml`
- `.github/workflows/aq26_earthdata_cmr_probe.yml`

## Run order

1. Merge this patch into the root of `AirQuality26_v2`.
2. Run **AQ26 LAQN Provider Probe V3.5** with:
   - `group_name: London`
   - `run_data_probe: false`
   - `commit_outputs: true`
3. If that passes, run it again with:
   - `run_data_probe: true`
   - leave site/species blank first.
4. Run **AQ26 NASA Earthdata CMR Probe** with:
   - `max_collections: 10`
   - `max_granules_per_collection: 3`
   - `commit_outputs: true`

## Earthdata API order for AQ26

1. CMR Search APIs first: discover collections and granules.
2. Earthdata Login next: authenticate selected downloads/subsets.
3. OPeNDAP/Hyrax third: subset gridded atmospheric products.
4. GIBS later: public map tiles and visual QA context.
5. DAAC-specific APIs later: only after CMR identifies the owning DAAC/product.

Do not start with Hyrax installation docs or generic NASA APIs.
