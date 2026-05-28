# AQ26 uploaded WEBM moving banners

This patch adds the user's six uploaded `desktop_banner_*.webm` files as the official AQ26 moving-banner assets.

## Assets

- `website/assets/banners/desktop_banner_1.webm`
- `website/assets/banners/desktop_banner_2.webm`
- `website/assets/banners/desktop_banner_3.webm`
- `website/assets/banners/desktop_banner_4.webm`
- `website/assets/banners/desktop_banner_5.webm`
- `website/assets/banners/desktop_banner_6.webm`

## Behaviour

The banner script injects:

- a full-width video hero banner;
- a moving evidence ticker;
- headline incinerator overlay statistics;
- reduced-motion accessibility support;
- public-safe wording for redacted pages.

The compact logo remains for favicon/touch icon usage. The visible page header should continue to use `air_quality_web.svg`.

## Run

Run:

```text
AQ26 Apply Uploaded WEBM Moving Banners
```

Then deploy with the operational dual-site workflow.

## Safety

Public text remains descriptive and does not claim regulatory breach, causality, legal conclusion or health diagnosis. Full diagnostics belong in `/unredacted/`.
