# AQ26 public site guard argument compatibility fix

This patch fixes the workflow error:

`aq26_public_site_guard_build.py: error: unrecognized arguments: --fail-on-blank`

The guard script now accepts all current/older workflow flags, repairs every core public page, creates mobile assets, favicon fallbacks, redirects and download placeholders, then validates that the public site is not blank.
