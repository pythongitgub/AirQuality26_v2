# AQ26 /test staging website

This adds a disposable staging site under `/test/` so experimental website builds can be reviewed without disturbing the live redacted root or the protected `/unredacted/` area.

Recommended first run:

- build_operational_site: true
- include_unredacted: true
- deploy_test: true
- dry_run: true
- remote_test_subdir: test

If the dry run is clean, rerun with `dry_run: false`.

Expected URLs:

- https://sccwebdesigntest.co.uk/test/index.html
- https://sccwebdesigntest.co.uk/test/test-index.html
- https://sccwebdesigntest.co.uk/test/incinerators.html
- https://sccwebdesigntest.co.uk/test/newhaven.html
- https://sccwebdesigntest.co.uk/test/weekly-update.html
- https://sccwebdesigntest.co.uk/test/unredacted/index.html

The workflow adds a yellow TEST/STAGING banner and noindex metadata.
