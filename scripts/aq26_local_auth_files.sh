#!/usr/bin/env bash
set -euo pipefail

: "${AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR:?Set AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR}"
: "${SCC_UNREDACTED_PASSWORD:?Set SCC_UNREDACTED_PASSWORD}"

mkdir -p auth_upload
htpasswd -Bbn aq26 "$SCC_UNREDACTED_PASSWORD" > auth_upload/.htpasswd
cat > auth_upload/.htaccess <<EOF
AuthType Basic
AuthName "AQ26 Unredacted"
AuthBasicProvider file
AuthUserFile ${AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR}/.htpasswd
Require valid-user
Options -Indexes
EOF

htpasswd -vb auth_upload/.htpasswd aq26 "$SCC_UNREDACTED_PASSWORD"
ls -la auth_upload
