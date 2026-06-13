#!/usr/bin/env bash
set -euo pipefail

: "${AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR:?Missing AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR}"
: "${SCC_UNREDACTED_PASSWORD:?Missing SCC_UNREDACTED_PASSWORD}"

mkdir -p auth_upload
htpasswd -Bbn aq26 "$SCC_UNREDACTED_PASSWORD" > auth_upload/.htpasswd
{
  echo 'AuthType Basic'
  echo 'AuthName "AQ26 Unredacted"'
  echo 'AuthBasicProvider file'
  echo "AuthUserFile ${AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR}/.htpasswd"
  echo 'Require valid-user'
  echo 'Options -Indexes'
} > auth_upload/.htaccess
htpasswd -vb auth_upload/.htpasswd aq26 "$SCC_UNREDACTED_PASSWORD"
ls -la auth_upload
