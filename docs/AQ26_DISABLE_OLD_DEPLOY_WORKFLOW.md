# Disabled obsolete workflow marker
#
# The old workflow .github/workflows/aq26_deploy_unredacted_site.yml should be deleted
# or renamed outside .github/workflows to avoid accidental runs.
#
# Use only:
#   AQ26 Deploy Public and Unredacted Sites
#
# Reason:
# - old workflow caused SSH/rsync confusion
# - new dual-site workflow applies no-blank pages, mobile nav, aliases, and password-protected unredacted deployment
