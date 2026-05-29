# AQ26 count stat-card final fix

This patch corrects legacy AQ26 page fragments that still display `86` in stat cards even though the weekly alert and overlay data correctly report 46 facilities.

It also removes redundant generated `SCC Nexus · AQ26` text next to the full SCC Nexus Air Quality Report logo.

Run `AQ26 Count Stat Card Final Fix` with public deploy dry-run first, then live if clean.
