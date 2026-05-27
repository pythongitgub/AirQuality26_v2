# AQ26 restore moving banners and legibility

This patch restores the moving banner/marquee feel and rebuilds the core public pages from a consistent template.

It keeps:
- white main header;
- full `air_quality_web.svg` visible logo;
- compact favicon only for browser/touch icons.

It fixes:
- raw/unformatted fallback pages;
- dark text on dark panels;
- public readiness pages dumping raw validation issue lists;
- missing moving banners.

Run:

```text
AQ26 Restore Moving Banners and Public Polish
```

Then deploy:

```text
AQ26 Deploy Public and Unredacted Sites
```

Use dry run first, then dry_run=false.
