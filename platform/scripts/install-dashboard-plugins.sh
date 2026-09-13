#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
plugin_source="${source_root}/platform/dashboard-plugins/aidee-fleet"

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
if [[ ! -f "${plugin_source}/dashboard/manifest.json" ]]; then
  fail "Fleet dashboard plugin is missing: ${plugin_source}"
fi

controller_home="$(getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6)"
hermes_home="${HERMES_HOME:-${controller_home}/.hermes}"
hermes_binary="${controller_home}/.local/bin/hermes"
plugins_dir="${hermes_home}/plugins"
destination="${plugins_dir}/aidee-fleet"

install -d \
  -m 0750 \
  -o "${AIDEE_CONTROLLER_USER}" \
  -g "${AIDEE_CONTROLLER_USER}" \
  "${plugins_dir}"

if [[ -L "${destination}" ]]; then
  rm -f "${destination}"
fi
if [[ -e "${destination}" && ! -d "${destination}" ]]; then
  fail "Refusing to replace unexpected plugin path: ${destination}"
fi

rm -rf "${destination}"
cp -a "${plugin_source}" "${destination}"
chown -R "${AIDEE_CONTROLLER_USER}:${AIDEE_CONTROLLER_USER}" "${destination}"
chmod -R a+rX "${destination}"

if [[ -x "${hermes_binary}" ]]; then
  # The positional argument expands inside the child shell.
  # shellcheck disable=SC2016
  runuser -u "${AIDEE_CONTROLLER_USER}" -- \
    env HOME="${controller_home}" HERMES_HOME="${hermes_home}" \
    bash -c 'printf "n\n" | "$1" plugins enable aidee-fleet' \
    aidee-enable-fleet \
    "${hermes_binary}"
fi

echo "Aidee Fleet dashboard plugin is installed."
