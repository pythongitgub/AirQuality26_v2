# AQ26 Unredacted 403 Fix

A 403 at `/unredacted/` usually means the remote directory exists but Apache cannot serve an index file, directory listing is blocked, or the `.htaccess` rules are malformed.

This patch fixes the deployment by:

- always building `site_unredacted/index.html`;
- adding `DirectoryIndex index.html`;
- creating `.htpasswd` with `htpasswd -B`;
- deploying files into `public_html/unredacted/` with a trailing slash;
- ensuring the remote directory exists before rsync;
- printing a remote file listing after real deployment.

Run the workflow first with `dry_run=true`, then with `dry_run=false`.

Login username: `aq26`
Password: value of `SCC_UNREDACTED_PASSWORD`.
