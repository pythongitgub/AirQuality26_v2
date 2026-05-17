# AQ26 build report syntax fix

This patch replaces `scripts/aq26_build_integrated_report.py`.

It fixes the workflow failure:

`SyntaxError: unterminated string literal`

Cause:
A previous generated fallback PDF byte string was split across a newline.

Fix:
The fallback line is now valid Python:

`pdf_path.write_bytes(b"%PDF-1.4\n% reportlab unavailable\n")`

Apply this patch, commit, and rerun the GitHub weekly workflow.
