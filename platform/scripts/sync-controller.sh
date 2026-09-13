#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_REPOSITORY="${AIDEE_REPOSITORY:-https://github.com/wetek/aidee.git}"
HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
upstream_dir="${HERMES_HOME}/aidee-upstream"
release=""
mode=""
approved=false

usage() {
  cat <<'EOF'
Usage:
  sync-controller.sh --release VERSION --preview
  sync-controller.sh --release VERSION --apply --approved

Preview fetches a tagged Aidee release and prints its release notes.
Apply refreshes versioned Aidee skills and records host update status.
This script never modifies root-owned host installation files.
EOF
}

fail() {
  echo "error: $*" >&2
  exit 1
}

while (( $# > 0 )); do
  case "$1" in
    --release)
      release="${2:-}"
      shift 2
      ;;
    --preview)
      mode="preview"
      shift
      ;;
    --apply)
      mode="apply"
      shift
      ;;
    --approved)
      approved=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "Unknown argument: $1"
      ;;
  esac
done

if [[ "${EUID}" -eq 0 ]]; then
  fail "Run this script as the unprivileged controller, not with sudo."
fi
if [[ ! "${release}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$ ]]; then
  fail "Release must look like v0.1.0-alpha.4."
fi
if [[ "${mode}" != "preview" && "${mode}" != "apply" ]]; then
  usage >&2
  fail "Choose --preview or --apply."
fi
if [[ "${mode}" == "apply" && "${approved}" != true ]]; then
  fail "Owner approval is required; pass --approved."
fi

releases_dir="${upstream_dir}/releases"
target="${releases_dir}/${release}"
install -d -m 0750 "${releases_dir}" "${HERMES_HOME}/skills"

if [[ -e "${target}" && ! -d "${target}/.git" ]]; then
  fail "Release cache exists but is incomplete: ${target}"
fi

if [[ ! -d "${target}/.git" ]]; then
  temporary="$(mktemp -d "${releases_dir}/.${release}.XXXXXX")"
  trap 'rm -rf "${temporary}"' EXIT
  git clone \
    --branch "${release}" \
    --depth 1 \
    "${AIDEE_REPOSITORY}" \
    "${temporary}"
  fetched_release="$(
    git -C "${temporary}" describe --tags --exact-match 2>/dev/null || true
  )"
  if [[ "${fetched_release}" != "${release}" ]]; then
    fail "Fetched source is not tagged ${release}."
  fi
  mv "${temporary}" "${target}"
  trap - EXIT
fi

release_notes="${target}/platform/releases/${release}.md"
if [[ ! -f "${release_notes}" ]]; then
  fail "Release notes are missing for ${release}."
fi

installed_release="not installed"
if [[ -d /opt/aidee/source/.git ]]; then
  installed_release="$(
    git -C /opt/aidee/source describe --tags --exact-match 2>/dev/null ||
      echo "unversioned"
  )"
fi
synced_release="none"
if [[ -f "${upstream_dir}/SYNCED_RELEASE" ]]; then
  synced_release="$(<"${upstream_dir}/SYNCED_RELEASE")"
fi

echo "Installed host release: ${installed_release}"
echo "Current knowledge release: ${synced_release}"
echo "Available release: ${release}"
echo
cat "${release_notes}"

if [[ "${mode}" == "preview" ]]; then
  echo
  echo "Preview complete. No active skills or host files changed."
  exit 0
fi

for skill_source in "${target}"/platform/shared-skills/*; do
  [[ -f "${skill_source}/SKILL.md" ]] || continue
  skill_name="$(basename "${skill_source}")"
  destination="${HERMES_HOME}/skills/${skill_name}"
  if [[ -e "${destination}" && ! -L "${destination}" ]]; then
    fail "Refusing to replace non-symlink skill: ${destination}"
  fi
  ln -sfn "${skill_source}" "${destination}"
done

ln -sfn "releases/${release}" "${upstream_dir}/current"
printf '%s\n' "${release}" > "${upstream_dir}/SYNCED_RELEASE"
chmod 0640 "${upstream_dir}/SYNCED_RELEASE"

if [[ "${installed_release}" != "${release}" ]]; then
  cat > "${upstream_dir}/HOST_UPDATE_REQUIRED.md" <<EOF
# Aidee host update required

Installed host release: ${installed_release}
Synced knowledge release: ${release}

The controller must not replace root-owned host files. Show the owner the
release notes and wait for approval before using the documented host updater.
EOF
else
  rm -f "${upstream_dir}/HOST_UPDATE_REQUIRED.md"
fi

echo
echo "Controller knowledge synced to ${release}."
if [[ "${installed_release}" != "${release}" ]]; then
  echo "The root-owned host installation still requires a separate update."
fi
