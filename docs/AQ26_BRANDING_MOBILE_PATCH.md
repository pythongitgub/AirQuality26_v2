# AQ26 branding, favicon and mobile navigation patch

This patch makes the generated site more suitable for public/client users.

## Adds

- `logo_web.svg` as the canonical AQ26/SCC Nexus site icon.
- SVG favicon.
- PNG fallbacks for browser/favicon use.
- Apple touch icon.
- Web manifest.
- Mobile hamburger navigation overlay.
- A safe post-build script that injects the required head tags into generated HTML.

## Why PNG is included as well as SVG

Modern browsers can use SVG favicons, but iOS/Apple touch icons are more reliable as PNG. This patch therefore uses the uploaded SVG as the source, keeps it as the favicon, and also supplies generated PNG icons.

## Best placement in the website workflow

Run this after the public site is generated and before deployment:

```bash
python scripts/aq26_apply_site_branding_mobile.py \
  --site-root site_public \
  --asset-source website/assets
```

If the unredacted site is also built in the same workflow:

```bash
python scripts/aq26_apply_site_branding_mobile.py \
  --site-root site_public \
  --asset-source website/assets \
  --include-unredacted
```

## Mobile menu

The JavaScript layer finds existing navigation links and creates a mobile hamburger menu. It hides the desktop pill/grid menu on small screens without needing to rewrite the site builder immediately.

Long-term, the site builder should generate semantic navigation:

```html
<nav aria-label="Main navigation">...</nav>
```

This script is a safe interim fix that works with generated pages.
