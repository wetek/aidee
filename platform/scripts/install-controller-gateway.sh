#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
service_name="hermes-gateway.service"
drop_in_dir="/etc/systemd/system/${service_name}.d"

fail() {
  echo "error: $*" >&2
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run this script with sudo after configuring the controller."
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

# Configure sudoers for autonomous host management
cat > "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}" <<EOF
${AIDEE_CONTROLLER_USER} ALL=(ALL) NOPASSWD: ALL
EOF
chmod 0440 "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}"

env \
  HOME="${controller_home}" \
  HERMES_HOME="${hermes_home}" \
  "${hermes_binary}" \
  gateway install \
  --force \
  --system \
  --run-as-user "${AIDEE_CONTROLLER_USER}" \
  --start-now \
  --start-on-login \
  </dev/null

install -d -m 0755 -o root -g root "${drop_in_dir}"
cat > "${drop_in_dir}/aidee-hardening.conf" <<EOF
[Service]
NoNewPrivileges=false
PrivateDevices=true
PrivateTmp=true
ProtectControlGroups=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ReadWritePaths=${controller_home} ${AIDEE_STATE_DIR} /run/aidee /etc/aidee
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
EOF

chmod 0644 "${drop_in_dir}/aidee-hardening.conf"
systemctl daemon-reload
systemctl restart "${service_name}"

if ! systemctl is-active --quiet "${service_name}"; then
  systemctl status "${service_name}" --no-pager >&2 || true
  fail "Controller gateway service did not start."
fi

echo "Aidee controller gateway is running as ${AIDEE_CONTROLLER_USER}."
