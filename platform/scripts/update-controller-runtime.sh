#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
HERMES_REPOSITORY="${HERMES_REPOSITORY:-https://github.com/NousResearch/hermes-agent.git}"
approved=false

if [[ "${1:-}" == "--approved" ]]; then
  approved=true
  shift
fi
if (( $# > 0 )) || [[ "${approved}" != true ]]; then
  echo "error: explicit owner approval is required; pass --approved" >&2
  exit 1
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
version="$(<"${script_dir}/../HERMES_VERSION")"
controller_home="$(getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6)"
hermes_home="${controller_home}/.hermes"
active_source="${hermes_home}/hermes-agent"
release_root="${hermes_home}/releases"
target="${release_root}/${version}"

controller_git() {
  runuser -u "${AIDEE_CONTROLLER_USER}" -- env HOME="${controller_home}" git "$@"
}

current=""
current_patch_valid=false
if [[ -d "${active_source}/.git" ]]; then
  current="$(
    controller_git -C "${active_source}" describe --tags --exact-match \
      2>/dev/null || true
  )"
  if runuser -u "${AIDEE_CONTROLLER_USER}" -- \
    "${script_dir}/apply-hermes-runtime-patch.sh" "${active_source}"
  then
    current_patch_valid=true
  fi
fi
hermes_binary="$(readlink -f "${controller_home}/.local/bin/hermes" 2>/dev/null || true)"
active_real="$(readlink -f "${active_source}" 2>/dev/null || true)"
if [[ "${current}" == "${version}" ]] &&
  [[ "${current_patch_valid}" == true ]] &&
  [[ "${hermes_binary}" == "${active_real}/venv/bin/hermes" ]] &&
  [[ -x "${hermes_binary}" ]]
then
  echo "Controller Hermes already matches ${version}."
  exit 0
fi

install -d -m 0750 -o "${AIDEE_CONTROLLER_USER}" -g "${AIDEE_CONTROLLER_USER}" \
  "${release_root}"
if [[ ! -d "${target}/.git" ]]; then
  temporary="${release_root}/.${version}.$$"
  trap 'rm -rf "${temporary}"' EXIT
  runuser -u "${AIDEE_CONTROLLER_USER}" -- env HOME="${controller_home}" \
    git clone --branch "${version}" --depth 1 "${HERMES_REPOSITORY}" "${temporary}"
  fetched="$(
    controller_git -C "${temporary}" describe --tags --exact-match \
      2>/dev/null || true
  )"
  [[ "${fetched}" == "${version}" ]] || {
    echo "error: fetched Hermes source is not tagged ${version}" >&2
    exit 1
  }
  runuser -u "${AIDEE_CONTROLLER_USER}" -- \
    "${script_dir}/apply-hermes-runtime-patch.sh" "${temporary}"
  mv "${temporary}" "${target}"
  trap - EXIT
fi
fetched="$(
  controller_git -C "${target}" describe --tags --exact-match \
    2>/dev/null || true
)"
if [[ "${fetched}" != "${version}" ]]; then
  echo "error: cached Hermes source is not the exact tag ${version}" >&2
  exit 1
fi
runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  "${script_dir}/apply-hermes-runtime-patch.sh" "${target}"

# The positional argument expands inside the child shell.
# shellcheck disable=SC2016
runuser -u "${AIDEE_CONTROLLER_USER}" -- env HOME="${controller_home}" \
  bash -c 'cd "$1" && printf "n\nn\n" | ./setup-hermes.sh' \
  aidee-update-controller "${target}"

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
  aidee-update-controller-web "${target}" "${hermes_home}"

if [[ -e "${active_source}" && ! -L "${active_source}" ]]; then
  legacy="${release_root}/legacy-$(date +%s)"
  mv "${active_source}" "${legacy}"
fi
runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  ln -sfn "releases/${version}" "${active_source}"

runuser -u "${AIDEE_CONTROLLER_USER}" -- \
  env HOME="${controller_home}" "${controller_home}/.local/bin/hermes" --version
echo "Controller Hermes updated to ${version}."
