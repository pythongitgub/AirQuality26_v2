AQ26 OVERHAUL COMPLETE V2 - UPLOAD NOTES

The last GitHub logs show the repository still did not contain:
  config/aq26_site_config.json

Earlier logs also showed:
  scripts/aq26_build_overhauled_site.py missing
  PyYAML missing in the standalone quality gate

This pack includes the whole required tree. Upload the CONTENTS of this ZIP to the repository root, preserving folders exactly:

  .github/workflows/aq26-site-overhaul-build-deploy.yml
  .github/workflows/aq26-site-quality-gate.yml
  config/aq26_site_config.json
  scripts/aq26_build_overhauled_site.py
  scripts/aq26_site_quality_gate.py
  scripts/aq26_deploy_hostinger_dual.py
  scripts/aq26_repo_preflight.py
  requirements.txt
  site_public/
  site_unredacted/

Do not upload the outer aq26_overhaul_v2 folder as a folder inside the repo.

Then run:
  AQ26 Website Overhaul Build and Deploy

The deployment preserves .htaccess and .htpasswd inside /unredacted/.
