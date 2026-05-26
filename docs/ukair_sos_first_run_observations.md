# UK-AIR SOS first run observations

- `/sos-ukair/api/v1/sos/kvp` returned 404 HTML/XML-like error pages.
- `/sos-ukair/sos` returned the real capabilities XML.
- Capabilities parser must use `observableProperty`.
- The previous run committed an uncompressed 12 MB XML file. V3.4 writes `.xml.gz` for artifact provenance and commits compact parsed JSON only.
- Observation harvesting should be a separate explicit-date-window step.
