#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
service_name="aidee-controller-dashboard.service"
service_path="/etc/systemd/system/${service_name}"

fail() {
  echo "error: $*" >&2
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run this script with sudo."
fi

if ! id "${AIDEE_CONTROLLER_USER}" >/dev/null 2>&1; then
  fail "Controller account does not exist: ${AIDEE_CONTROLLER_USER}"
fi

controller_home="$(getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6)"
hermes_binary="${controller_home}/.local/bin/hermes"
hermes_home="${controller_home}/.hermes"

if [[ ! -x "${hermes_binary}" ]]; then
  fail "Hermes is not installed for ${AIDEE_CONTROLLER_USER}."
fi

cat > "${service_path}" <<EOF
[Unit]
Description=Aidee controller dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${AIDEE_CONTROLLER_USER}
Group=${AIDEE_CONTROLLER_USER}
Environment=HOME=${controller_home}
Environment=HERMES_HOME=${hermes_home}
WorkingDirectory=${controller_home}
ExecStart=${hermes_binary} dashboard --host 127.0.0.1 --port 9119 --no-open
Restart=on-failure
RestartSec=5
UMask=0077

NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectControlGroups=true
ProtectHome=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=strict
ReadWritePaths=${controller_home} ${AIDEE_STATE_DIR}/fleet/controller
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "${service_path}"
systemctl daemon-reload
systemctl enable --now "${service_name}"

if ! systemctl is-active --quiet "${service_name}"; then
  systemctl status "${service_name}" --no-pager >&2 || true
  fail "Controller dashboard service did not start."
fi

echo "Aidee controller dashboard is running on 127.0.0.1:9119."
echo "Reach it through an SSH tunnel. Do not open port 9119 publicly."
