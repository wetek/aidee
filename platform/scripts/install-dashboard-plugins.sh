#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
fleet_source="${source_root}/platform/dashboard-plugins/aidee-fleet"
overview_source="${source_root}/platform/dashboard-plugins/aidee-overview"
onboarding_source="${source_root}/platform/hermes-plugins/aidee-onboarding"

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
if [[ ! -f "${fleet_source}/dashboard/manifest.json" ]]; then
  fail "Fleet dashboard plugin is missing: ${fleet_source}"
fi
if [[ ! -f "${overview_source}/dashboard/manifest.json" ]]; then
  fail "Fleet overview plugin is missing: ${overview_source}"
fi
if [[ ! -f "${onboarding_source}/plugin.yaml" ]]; then
  fail "Onboarding plugin is missing: ${onboarding_source}"
fi

controller_home="$(getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6)"
hermes_home="${HERMES_HOME:-${controller_home}/.hermes}"
hermes_binary="${controller_home}/.local/bin/hermes"
plugins_dir="${hermes_home}/plugins"

install -d \
  -m 0750 \
  -o "${AIDEE_CONTROLLER_USER}" \
  -g "${AIDEE_CONTROLLER_USER}" \
  "${plugins_dir}"

install_user_plugin() {
  local plugin_source="$1"
  local plugin_name="$2"
  local destination="${plugins_dir}/${plugin_name}"

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
}

enable_user_plugin() {
  local plugin_name="$1"
  if [[ ! -x "${hermes_binary}" ]]; then
    return 0
  fi
  runuser -u "${AIDEE_CONTROLLER_USER}" -- \
    env HOME="${controller_home}" HERMES_HOME="${hermes_home}" \
    "${hermes_binary}" plugins enable "${plugin_name}" \
    --no-allow-tool-override
}

install_user_plugin "${overview_source}" "aidee-overview"
install_user_plugin "${fleet_source}" "aidee-fleet"
install_user_plugin "${onboarding_source}" "aidee-onboarding"
enable_user_plugin "aidee-overview"
enable_user_plugin "aidee-fleet"
enable_user_plugin "aidee-onboarding"

echo "Aidee Hermes plugins are installed."
