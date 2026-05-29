# AQ26 Final Brand Header Weekly Polish

This patch is a post-build polish step for the live AQ26 public/unredacted sites.

It fixes two visible issues:

1. Removes the extra text next to the full `SCC Nexus Air Quality Report` header logo.
2. Rewrites favicon references so browsers prefer `/favicon.ico` and `/favicon.svg` with a cache-busting version.

It also checks that the redacted public homepage still contains:
- weekly alert panel
- moving WEBM banner
- favicon references
- full header logo

## Recommended run

Run:

`AQ26 Final Brand Header Weekly Polish`

First:

- `deploy_public = true`
- `deploy_unredacted = false`
- `dry_run = true`

If the file list is sensible, rerun with:

- `dry_run = false`

## Cache testing

After live deploy, test:

- `https://sccwebdesigntest.co.uk/favicon.ico?v=aq26-final-brand-20260529`
- `https://sccwebdesigntest.co.uk/favicon.svg?v=aq26-final-brand-20260529`
- `https://sccwebdesigntest.co.uk/index.html?v=aq26-final-brand-20260529`

Chrome and Android can cache old favicons aggressively. Use a private/incognito window for verification.
