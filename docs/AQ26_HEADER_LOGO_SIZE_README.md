# AQ26 header logo size patch

This patch preserves the successful footer/cookie/history deployment and increases the AQ26 header logo size.

## Generated CSS size changes

Desktop:
- `.logo.aq-logo`: `180px x 92px`

Mobile:
- `.logo.aq-logo`: `150px x 78px`

It also slightly increases the header padding.

## Apply

Commit this file:

- `scripts/aq26_weeklyv2_build_sccnexus_site.py`
- `docs/AQ26_HEADER_LOGO_SIZE_README.md`
- `PATCH_CONTENTS.json`

Then rerun:

Actions → AQ26 WeeklyV2 SCC Nexus Website

Use:
- `remote_subdir`: `airquality26`
- `deploy_to_hostinger`: `true`
