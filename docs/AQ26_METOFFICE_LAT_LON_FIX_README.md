# AQ26 Met Office lat/lon fix

This patch fixes the Met Office Land Observations nearest request.

The smoke-test artifact showed `MET_OFFICE_API_KEY` with the documented `apikey` header was accepted,
but the API returned:

`Either a geohash or lat and lon values must be provided.`

The old code used `latitude` and `longitude`. This patch uses `lat` and `lon`.

It also:
- throttles GDELT calls to reduce 429 errors
- runs redaction before and after building the final report bundle
- includes redaction audit in the final ZIP
- excludes the SHA256 ledger from hashing itself
