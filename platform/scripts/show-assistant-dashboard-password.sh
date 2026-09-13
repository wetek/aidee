#!/usr/bin/env bash
set -Eeuo pipefail

assistant_id="${1:-}"
if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo in your SSH terminal" >&2
  exit 1
fi
if [[ ! "${assistant_id}" =~ ^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$ ]]; then
  echo "error: invalid assistant ID" >&2
  exit 1
fi

password_file="/var/lib/aidee/secrets/assistants/${assistant_id}/dashboard-initial-password"
if [[ ! -f "${password_file}" ]]; then
  echo "error: dashboard password not found for ${assistant_id}" >&2
  exit 1
fi

echo "Dashboard username: aidee"
printf 'Dashboard password: '
cat "${password_file}"
echo
echo "Do not paste this password into chat."
