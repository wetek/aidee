#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_CODE_DIR="${AIDEE_CODE_DIR:-/opt/aidee}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
AIDEE_CONFIG_DIR="${AIDEE_CONFIG_DIR:-/etc/aidee}"

fail() {
  echo "error: $*" >&2
  exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run this script with sudo."
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID}" != "ubuntu" ]]; then
  fail "This pilot supports Ubuntu only. Found ${PRETTY_NAME}."
fi

case "${VERSION_ID}" in
  24.04|26.04) ;;
  *) fail "This pilot supports Ubuntu 24.04 and 26.04. Found ${PRETTY_NAME}." ;;
esac

if [[ "$(dpkg --print-architecture)" != "amd64" ]]; then
  fail "This pilot supports amd64 hosts only."
fi

if [[ ! "${AIDEE_CONTROLLER_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  fail "AIDEE_CONTROLLER_USER is not a valid Linux user name."
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get upgrade -y
apt-get install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  jq \
  openssl \
  python3 \
  python3-jsonschema \
  python3-yaml \
  ripgrep \
  rsync \
  sudo \
  unattended-upgrades \
  unzip \
  xz-utils

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-${VERSION_CODENAME}}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y \
  containerd.io \
  docker-buildx-plugin \
  docker-ce \
  docker-ce-cli \
  docker-compose-plugin

systemctl enable --now docker

install -d -m 0755 -o root -g root "${AIDEE_STATE_DIR}"

if ! id "${AIDEE_CONTROLLER_USER}" >/dev/null 2>&1; then
  useradd \
    --create-home \
    --home-dir "${AIDEE_STATE_DIR}/controller-home" \
    --user-group \
    --shell /bin/bash \
    "${AIDEE_CONTROLLER_USER}"
fi

install -d -m 0755 -o root -g root "${AIDEE_CODE_DIR}"
install -d -m 0755 -o root -g root "${AIDEE_CONFIG_DIR}"
install -d -m 0750 -o root -g "${AIDEE_CONTROLLER_USER}" "${AIDEE_STATE_DIR}"

for directory in controller fleet runtime backups; do
  install -d \
    -m 0750 \
    -o "${AIDEE_CONTROLLER_USER}" \
    -g "${AIDEE_CONTROLLER_USER}" \
    "${AIDEE_STATE_DIR}/${directory}"
done

install -d \
  -m 0700 \
  -o "${AIDEE_CONTROLLER_USER}" \
  -g "${AIDEE_CONTROLLER_USER}" \
  "${AIDEE_STATE_DIR}/secrets"

dpkg-reconfigure -f noninteractive unattended-upgrades

echo
echo "Aidee host bootstrap completed."
echo "Controller user: ${AIDEE_CONTROLLER_USER}"
echo "Code directory: ${AIDEE_CODE_DIR}"
echo "State directory: ${AIDEE_STATE_DIR}"
echo
echo "The controller has not been granted sudo or Docker access."
echo "Install the audited Aidee administration helper before provisioning assistants."

if [[ -f /var/run/reboot-required ]]; then
  echo "A reboot is required before continuing."
fi
