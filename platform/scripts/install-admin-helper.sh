#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
source_script="/opt/aidee/source/platform/admin/aidee_admin.py"
install_dir="/usr/local/lib/aidee"
installed_script="${install_dir}/aidee-admin"
service="aidee-admin.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo on the Aidee host" >&2
  exit 1
fi
if [[ ! -f "${source_script}" ]]; then
  echo "error: administration helper source is missing" >&2
  exit 1
fi
if ! id "${AIDEE_CONTROLLER_USER}" >/dev/null 2>&1; then
  echo "error: controller account does not exist" >&2
  exit 1
fi

apt-get update
apt-get install -y python3-jsonschema python3-yaml

install -d -m 0755 -o root -g root "${install_dir}"
install -d -m 0755 -o root -g root /etc/aidee/images
install -m 0755 -o root -g root "${source_script}" "${installed_script}"

cat > "/etc/systemd/system/${service}" <<EOF
[Unit]
Description=Aidee narrow administration helper
After=docker.service tailscaled.service
Requires=docker.service

[Service]
Type=simple
User=root
Group=root
ExecStartPre=/bin/chown root:${AIDEE_CONTROLLER_USER} /run/aidee
ExecStart=/usr/bin/python3 ${installed_script}
Restart=on-failure
RestartSec=5
RuntimeDirectory=aidee
RuntimeDirectoryMode=0750
UMask=0077

NoNewPrivileges=true
PrivateTmp=true
ProtectControlGroups=true
ProtectHome=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=strict
ReadOnlyPaths=/opt/aidee/source
ReadWritePaths=/var/lib/aidee /run/aidee /etc/aidee/images
RestrictAddressFamilies=AF_UNIX
RestrictSUIDSGID=true
CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER
AmbientCapabilities=

[Install]
WantedBy=multi-user.target
EOF

chmod 0644 "/etc/systemd/system/${service}"
systemctl daemon-reload
systemctl enable --now "${service}"

for _ in {1..20}; do
  if [[ -S /run/aidee/admin.sock ]]; then
    echo "Aidee administration helper is ready."
    exit 0
  fi
  sleep 1
done

systemctl status "${service}" --no-pager >&2 || true
echo "error: administration helper socket was not created" >&2
exit 1
