# AQ26 redaction diagnostic patch

This patch does not weaken the redaction gate. It keeps the workflow failing when a runtime secret value is detected, but it now prints and uploads a safe summary showing only the file path, leak type and SHA256 hash of the leaked value.

After applying, rerun the production workflow with deploy_to_hostinger=false and dry_run=true. If the gate fails again, download the `aq26-redaction-failure-summary` artifact and remove/regenerate the listed files before deploying.
