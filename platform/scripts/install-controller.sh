#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
HERMES_REPOSITORY="${HERMES_REPOSITORY:-https://github.com/NousResearch/hermes-agent.git}"

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

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
hermes_version="$(<"${script_dir}/../HERMES_VERSION")"

if [[ ! "${hermes_version}" =~ ^v[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}$ ]]; then
  fail "Invalid Hermes version: ${hermes_version}"
fi

controller_home="$(getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6)"
if [[ -z "${controller_home}" || ! -d "${controller_home}" ]]; then
  fail "Controller home directory is unavailable."
fi

hermes_home="${controller_home}/.hermes"
hermes_source="${hermes_home}/hermes-agent"

if [[ -e "${hermes_source}" ]]; then
  fail "Hermes source already exists: ${hermes_source}"
fi

install -d \
  -m 0750 \
  -o "${AIDEE_CONTROLLER_USER}" \
  -g "${AIDEE_CONTROLLER_USER}" \
  "${hermes_home}"

runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  env HOME="${controller_home}" \
  git clone \
    --branch "${hermes_version}" \
    --depth 1 \
    "${HERMES_REPOSITORY}" \
    "${hermes_source}"

# The positional argument expands inside the child shell.
# shellcheck disable=SC2016
runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  env HOME="${controller_home}" \
  bash -c 'cd "$1" && printf "n\n" | ./setup-hermes.sh' \
  aidee-install-controller \
  "${hermes_source}"

# Install the managed Node runtime and web dependencies without browser binaries.
# The positional arguments expand inside the child shell.
# shellcheck disable=SC2016
runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  env HOME="${controller_home}" HERMES_HOME="${hermes_home}" \
  bash -c '
    cd "$1"
    ./scripts/install.sh \
      --stage node-deps \
      --non-interactive \
      --skip-browser \
      --skip-computer-use \
      --dir "$1" \
      --hermes-home "$2"
    export PATH="$2/node/bin:$PATH"
    cd web
    npm run build
  ' \
  aidee-install-controller-web \
  "${hermes_source}" \
  "${hermes_home}"

hermes_binary="${controller_home}/.local/bin/hermes"
if [[ ! -x "${hermes_binary}" ]]; then
  fail "Hermes installation did not create ${hermes_binary}"
fi

controller_soul="${AIDEE_STATE_DIR}/fleet/controller/SOUL.md"
if [[ ! -f "${controller_soul}" ]]; then
  fail "Initialize fleet state before installing the controller."
fi

runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  ln -sfn "${controller_soul}" "${hermes_home}/SOUL.md"

for skill_source in "${script_dir}"/../shared-skills/*; do
  [[ -f "${skill_source}/SKILL.md" ]] || continue
  skill="$(basename "${skill_source}")"
  runuser -u "${AIDEE_CONTROLLER_USER}" -- \
    ln -sfn "${skill_source}" "${hermes_home}/skills/${skill}"
done

"${script_dir}/install-dashboard-plugins.sh"

runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  env HOME="${controller_home}" \
  "${hermes_binary}" --version

echo "Aidee controller runtime installed with Hermes ${hermes_version}."
echo "No model, messaging, or service credentials were requested."
