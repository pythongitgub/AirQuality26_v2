# AQ26 artifact and website-weight reduction patch

This patch reduces the weekly GitHub Actions artifact and live website size without weakening provenance.

## What was causing the size

The previous artifact upload path was broad enough to include generated outputs, public site, unredacted site and test site together. In the uploaded run log it selected 1,795 files and produced a 792 MB artifact.

The uploaded repo/site inspection showed the dominant contributors were:

- duplicated public + unredacted evidence ZIPs: about 54.4 MB each in the live website tree;
- generated historical backfill outputs: about 216 MB locally, mostly repeated JSON inventories and official/satellite catalogues;
- repeated large SVG logo/favicon files: about 1.6 MB each, repeated across public/unredacted/website folders;
- banners/video are present but much smaller than the evidence ZIP and repeated generated outputs.

## New professional artifact policy

Normal weekly run uploads only `aq26-weekly-review-pack`, containing:

- PDF/MD weekly report;
- redaction/provenance/readiness gates;
- SHA256 ledgers;
- current site data JSON/CSV;
- artifact size audit CSV/JSON.

The full evidence ZIP is now a separate optional short-retention artifact controlled by:

`upload_full_evidence_artifact: true`

Keep that false for normal runs. Use true only when Drive upload is unavailable and you need to manually download the full bundle.

## Live website policy

Large ZIP archives are moved out of `site_public`, `site_unredacted`, and `site_test` before deployment. A `.metadata.json` stub is left in place explaining where the bundle should live: Google Shared Drive or optional short-retention Actions artifact.

## Drive shortcut folder

A Google Drive folder of shortcuts can help humans navigate duplicates, but shortcuts are not enough for reliable deduplication. The robust approach is a Drive inventory with IDs, md5Checksum, size, mimeType, createdTime, modifiedTime and shortcut target IDs. Deduplicate by checksum first, then by normalised title/date.

