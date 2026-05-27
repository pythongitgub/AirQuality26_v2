# AQ26 white header legibility fix

This patch repairs the over-dark text and low contrast introduced by prior branding CSS.

It keeps the compact symbol for favicon/touch icons, uses `air_quality_web.svg` for visible headers, forces hero text to white, uses white content cards with navy text, and adds a mobile hamburger fallback.

Run:

1. `AQ26 Apply White Header Legibility Fix`
2. `AQ26 Deploy Public and Unredacted Sites` with `dry_run=true`
3. rerun deploy with `dry_run=false`

Then hard refresh or test in an incognito window.
