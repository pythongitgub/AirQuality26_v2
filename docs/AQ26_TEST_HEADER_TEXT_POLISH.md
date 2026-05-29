# AQ26 test header text commit fix

This patch fixes the previous `/test/` header-polish workflow failure:

`cannot pull with rebase: You have unstaged changes`

The replacement workflow uses a safer sequence:

1. fetch/rebase before generating
2. build operational site
3. build `site_test/`
4. remove the text beside the header logo
5. validate test pages
6. commit safe staging files
7. `git pull --rebase --autostash`
8. push
9. deploy `/test/`

It also removes `.htpasswd` before commit and validates that no password file is staged.
