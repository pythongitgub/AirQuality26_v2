# AQ26 UK-AIR SOS V3.4 verified provider patch

## What the first run proved

The first UK-AIR SOS probe was successful.

The verified endpoint was:

`https://uk-air.defra.gov.uk/sos-ukair/sos?service=SOS&request=GetCapabilities&AcceptVersions=2.0.0`

It returned:

- HTTP 200
- `application/xml;charset=UTF-8`
- 12,404,625 bytes of capabilities XML
- SHA-256 `d44434df39a1f8aaab3ce7a940e08b80df0ed5b423d4c3113544b1b460303f65`
- 9 supported SOS operations
- 2,884 offerings / station-process links

The earlier parser missed pollutant properties because the XML uses `observableProperty`, not only `observedProperty`.

## What this patch changes

- Prefers the verified `/sos-ukair/sos` endpoint.
- Parses `observableProperty` correctly.
- Creates compact pollutant, station and offering inventories.
- Compresses raw capabilities XML instead of requiring a huge raw XML commit.
- Adds temporal/science provenance fields.
- Adds an optional tiny GetObservation probe, disabled by default.
- Adds `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to reduce upcoming GitHub Actions Node 20 deprecation risk.

## Upload / merge

Upload the contents of this ZIP into the repository root.

## Recommended run

Actions → `AQ26 UK-AIR SOS Provider Probe V3.4`

Use:

- `run_observation_probe`: `false`

After the capabilities run succeeds, run a small observation probe:

- `run_observation_probe`: `true`
- `observation_start_date`: `2024-07-22`
- `observation_end_date`: `2024-07-23`
- `observation_limit`: `3`

## Science note

Capabilities readiness is not the same as validated observation harvesting. Do not add UK-AIR SOS into the public pollutant time-series until the observation payload parser and QA rules are confirmed.
