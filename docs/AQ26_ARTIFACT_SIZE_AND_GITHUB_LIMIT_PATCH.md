# AQ26 artifact size and GitHub 100 MB file limit patch

This patch prevents the production workflow from committing large generated ZIP files
under `site_public/downloads/` or `site_unredacted/downloads/`.

## Why

GitHub rejects individual files larger than 100 MB. The previous run built correctly
but failed when the commit step tried to push:

`site_public/downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip`

The workflow artifact was also unnecessarily large because it uploaded full site
folders plus output folders with duplicate ZIP/media packages.

## Behaviour after this patch

- The full controlled evidence ZIP remains available as the GitHub Actions artifact.
- The website publishes lightweight public downloads: PDF, Markdown report and JSON ledgers.
- The final ZIP is not copied into public or unredacted website downloads.
- Generated site ZIPs/media packages are not included recursively inside the evidence bundle.
- The commit step deletes and unstages any generated `.zip` files under site folders.
- The uploaded artifact is a lean package, usually much smaller than the previous 524 MB artifact.

For Google Drive backup, keep `upload_to_drive=false` until `GDRIVE_FOLDER_ID` points to a Shared Drive
folder accessible by the service account.
