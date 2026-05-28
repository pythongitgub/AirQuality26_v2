# AQ26 Moving Banners Enforcement Patch

This patch restores visible movement across the AQ26 public and unredacted sites.

It adds:

- `website/assets/aq26_moving_banners.css`
- `website/assets/aq26_moving_banners.js`
- `scripts/aq26_apply_moving_banners.py`
- `.github/workflows/aq26_apply_moving_banners.yml`

The banner layer is intentionally safe and accessible: it uses visual motion only, does not load external services, and respects `prefers-reduced-motion`.

Run `AQ26 Apply Moving Banners`, then deploy the public and unredacted sites.
