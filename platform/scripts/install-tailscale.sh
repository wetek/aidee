#!/usr/bin/env bash
set -Eeuo pipefail

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

key_url="https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.noarmor.gpg"
list_url="https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.tailscale-keyring.list"

curl -fsSL "${key_url}" \
  -o /usr/share/keyrings/tailscale-archive-keyring.gpg
curl -fsSL "${list_url}" \
  -o /etc/apt/sources.list.d/tailscale.list

chmod 0644 \
  /usr/share/keyrings/tailscale-archive-keyring.gpg \
  /etc/apt/sources.list.d/tailscale.list

apt-get update
apt-get install -y tailscale
systemctl enable --now tailscaled

tailscale version
echo
echo "Tailscale is installed but not authenticated."
echo "Run 'sudo tailscale up' and open the displayed URL yourself."
echo "Never send a Tailscale auth key or login URL through chat."
