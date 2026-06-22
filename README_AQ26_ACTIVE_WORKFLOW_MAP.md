# AQ26 active workflow map

AQ26 now uses a small active workflow set so old patch/deploy jobs cannot overwrite the publication website.

## Active workflows

| Workflow file | Purpose | Keep active |
|---|---|---|
| `.github/workflows/aq26-canonical-site-deploy.yml` | Builds the publication-grade public, unredacted and test site; audits SEO/assets/redaction; deploys to Hostinger. | Yes |
| `.github/workflows/aq26-drive-forensic-evidence-audit.yml` | Read-only Google Drive evidence-lake inventory and publication risk screen. | Yes |
| `.github/workflows/aq26_weekly_v2.yml` | Weekly controlled evidence harvest and redaction-checked bundle generation. | Yes |
| `.github/workflows/aq26-hostinger-ssh-preflight.yml` | Manual SSH connectivity check only. | Yes |
| `.github/workflows/aq26-retire-superseded-workflows.yml` | Manual safety workflow to move any remaining old workflows out of active Actions. | Yes |

## Retired conflicting workflows

Legacy deploy/polish/restore workflows that could overwrite formatting, pages, logos, banners, SEO, analytics or `/unredacted/` have been removed from the active workflow folder. They remain in Git history and can be recovered if genuinely needed.

## Publication rule

All future public website changes should flow through:

```text
configs/aq26_canonical_site.yml
scripts/aq26_build_canonical_site.py
scripts/aq26_site_full_audit.py
.github/workflows/aq26-canonical-site-deploy.yml
```

The public site must include consistent formatting, AQ26 logo/header, banner/hero assets, complete pages, sitemap, robots.txt, canonical URLs, metadata, JSON-LD, Apple/Android icons, web manifest and Google Analytics. Protected material belongs only under `/unredacted/` and must be noindex/password protected.
