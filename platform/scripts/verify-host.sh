#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_CODE_DIR="${AIDEE_CODE_DIR:-/opt/aidee}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
AIDEE_CONFIG_DIR="${AIDEE_CONFIG_DIR:-/etc/aidee}"
errors=0

pass() {
  printf 'PASS  %s\n' "$*"
}

fail() {
  printf 'FAIL  %s\n' "$*"
  errors=$((errors + 1))
}

if command -v docker >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
  pass "Docker Engine is running."
else
  fail "Docker Engine is not installed or running."
fi

if sudo docker compose version >/dev/null 2>&1; then
  pass "Docker Compose is available."
else
  fail "Docker Compose is unavailable."
fi

if id "${AIDEE_CONTROLLER_USER}" >/dev/null 2>&1; then
  pass "Controller account ${AIDEE_CONTROLLER_USER} exists."
else
  fail "Controller account ${AIDEE_CONTROLLER_USER} does not exist."
fi

controller_groups="$(id -nG "${AIDEE_CONTROLLER_USER}" 2>/dev/null || true)"
if [[ " ${controller_groups} " == *" sudo "* || " ${controller_groups} " == *" docker "* ]]; then
  fail "Controller account belongs to sudo or docker group."
else
  pass "Controller account has no sudo or Docker group membership."
fi

if sudo -u "${AIDEE_CONTROLLER_USER}" sudo -n true >/dev/null 2>&1; then
  fail "Controller account has passwordless sudo access."
else
  pass "Controller account cannot invoke unrestricted passwordless sudo."
fi

for directory in "${AIDEE_CODE_DIR}" "${AIDEE_CONFIG_DIR}" "${AIDEE_STATE_DIR}"; do
  if [[ -d "${directory}" ]]; then
    pass "Directory exists: ${directory}"
  else
    fail "Directory is missing: ${directory}"
  fi
done

if [[ "$(sudo stat -c '%U:%G:%a' "${AIDEE_STATE_DIR}/secrets" 2>/dev/null || true)" == "${AIDEE_CONTROLLER_USER}:${AIDEE_CONTROLLER_USER}:700" ]]; then
  pass "Secret directory owner and mode are correct."
else
  fail "Secret directory must be owned by ${AIDEE_CONTROLLER_USER} with mode 700."
fi

if systemctl is-enabled unattended-upgrades >/dev/null 2>&1; then
  pass "Unattended security upgrades are enabled."
else
  fail "Unattended security upgrades are not enabled."
fi

if [[ -f /var/run/reboot-required ]]; then
  fail "The host requires a reboot."
else
  pass "No reboot is pending."
fi

echo
echo "Host verification: ${errors} failure(s)."

if (( errors > 0 )); then
  exit 1
fi
