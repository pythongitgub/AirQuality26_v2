# AQ26 deployment assurance and controlled-review wording patch

This patch makes the workflow verify the public deployment after Hostinger upload and tightens the institutional/expert wording.

## Public deployment target

Default verified public URL:

`https://sccwebdesigntest.co.uk/airquality26`

The workflow input is:

`public_base_url`

Use this value when manually running the workflow:

`https://sccwebdesigntest.co.uk/airquality26`

The workflow deploys into:

`$HOSTINGER_PUBLIC_HTML_DIR/$remote_subdir`

With:

`remote_subdir = airquality26`

## Public verification step

After rsync deployment, the workflow now fetches and validates:

- `/index.html`
- `/privacy.html`
- `/cookies.html`
- `/data/weekly_index.json`

It verifies the live site contains:

- `AQ26 Environmental Intelligence Observatory`
- `air_quality_web.svg`
- `cookie-banner`
- valid `weekly_index.json`

If these checks fail, the workflow fails.

## Institutional and expert wording

The site wording is tightened to say:

- prepared for controlled expert and institutional review
- no WHO/UNEP/EEA/C40 endorsement or representation is claimed
- no endorsement by named experts is claimed
- no causal attribution is claimed unless evidence gates pass

This respects the project goal while avoiding overclaiming or misrepresenting affiliation.
