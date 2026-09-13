#!/usr/bin/env bash
set -Eeuo pipefail

release=""
owner_name=""
approved=false

usage() {
  cat <<'EOF'
Usage:
  sudo ./platform/scripts/update-host.sh \
    --release VERSION \
    --owner-name NAME \
    --approved

Run from a clean checkout of the target tagged release.
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --release)
      release="${2:-}"
      shift 2
      ;;
    --owner-name)
      owner_name="${2:-}"
      shift 2
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
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo" >&2
  exit 1
fi
if [[ "${approved}" != true ]]; then
  echo "error: owner approval is required; pass --approved" >&2
  exit 1
fi
if [[ ! "${release}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$ ]]; then
  echo "error: invalid release" >&2
  exit 1
fi
if [[ -z "${owner_name}" || "${owner_name}" == *$'\n'* ]]; then
  echo "error: owner name must be one non-empty line" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
candidate_root="$(cd -- "${script_dir}/../.." && pwd)"
candidate_tag="$(
  git -C "${candidate_root}" describe --tags --exact-match 2>/dev/null || true
)"
if [[ "${candidate_tag}" != "${release}" ]]; then
  echo "error: candidate checkout is not tagged ${release}" >&2
  exit 1
fi
if [[ -n "$(git -C "${candidate_root}" status --porcelain)" ]]; then
  echo "error: candidate checkout is not clean" >&2
  exit 1
fi
if [[ "$(<"${candidate_root}/LATEST")" != "${release}" ]]; then
  echo "error: LATEST does not match ${release}" >&2
  exit 1
fi

release_dir="/opt/aidee/releases/${release}"
if [[ ! -d "${release_dir}/.git" ]]; then
  install -d -m 0755 -o root -g root /opt/aidee/releases
  git clone \
    --branch "${release}" \
    --depth 1 \
    https://github.com/wetek/aidee.git \
    "${release_dir}"
fi

installed_source="/opt/aidee/source"
if [[ -d "${installed_source}" && ! -L "${installed_source}" ]]; then
  previous_release="$(
    git -C "${installed_source}" describe --tags --exact-match 2>/dev/null ||
      echo "legacy"
  )"
  previous_dir="/opt/aidee/releases/${previous_release}"
  if [[ -e "${previous_dir}" ]]; then
    echo "error: previous release archive already exists: ${previous_dir}" >&2
    exit 1
  fi
  mv "${installed_source}" "${previous_dir}"
fi

ln -sfn "releases/${release}" "${installed_source}"

jq -n --arg name "${owner_name}" '{name: $name}' > /etc/aidee/owner.json
chmod 0644 /etc/aidee/owner.json

"${installed_source}/platform/scripts/install-admin-helper.sh"
"${installed_source}/platform/scripts/build-assistant-image.sh"
"${installed_source}/platform/scripts/validate-assistant-image.sh"

echo "Aidee host updated to ${release}."
echo "Controller knowledge sync remains a separate owner-approved action."
