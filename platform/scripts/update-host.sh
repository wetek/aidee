#!/usr/bin/env bash
set -Eeuo pipefail

release=""
owner_name=""
approved=false
mode=""
AIDEE_REPOSITORY="${AIDEE_REPOSITORY:-https://github.com/wetek/aidee.git}"

usage() {
  cat <<'EOF'
Usage:
  sudo ./platform/scripts/update-host.sh --release VERSION --preview
  sudo ./platform/scripts/update-host.sh --release VERSION --apply --approved \
    [--owner-name NAME]

Preview fetches and validates the exact tag but changes no active state.
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
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo" >&2
  exit 1
fi
if [[ "${mode}" != "preview" && "${mode}" != "apply" ]]; then
  echo "error: choose --preview or --apply" >&2
  exit 1
fi
if [[ "${mode}" == "apply" && "${approved}" != true ]]; then
  echo "error: owner approval is required; pass --approved" >&2
  exit 1
fi
if [[ ! "${release}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$ ]]; then
  echo "error: invalid release" >&2
  exit 1
fi
if [[ "${owner_name}" == *$'\n'* ]]; then
  echo "error: owner name must be one line" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
candidate_root="$(cd -- "${script_dir}/../.." && pwd)"
candidate_tag="$(
  git -C "${candidate_root}" describe --tags --exact-match 2>/dev/null || true
)"
release_dir="/opt/aidee/releases/${release}"
if [[ "${candidate_tag}" == "${release}" ]] &&
  [[ -z "$(git -C "${candidate_root}" status --porcelain)" ]]
then
  if [[ "${candidate_root}" != "${release_dir}" ]]; then
    install -d -m 0755 -o root -g root /opt/aidee/releases
    if [[ ! -e "${release_dir}" ]]; then
      git -c advice.detachedHead=false clone \
        --local --branch "${release}" "${candidate_root}" "${release_dir}"
    fi
  fi
else
  install -d -m 0755 -o root -g root /opt/aidee/releases
fi

if [[ ! -d "${release_dir}/.git" ]]; then
  echo "Fetching Aidee ${release}..."
  temporary="/opt/aidee/releases/.${release}.$$"
  trap 'rm -rf "${temporary}"' EXIT
  git -c advice.detachedHead=false clone \
    --branch "${release}" \
    --depth 1 \
    "${AIDEE_REPOSITORY}" \
    "${temporary}"
  mv "${temporary}" "${release_dir}"
  trap - EXIT
else
  echo "Using cached Aidee ${release}."
fi
echo "Starting ${mode} for ${release}."

fetched_tag="$(git -C "${release_dir}" describe --tags --exact-match 2>/dev/null || true)"
if [[ "${fetched_tag}" != "${release}" ]] ||
  [[ -n "$(git -C "${release_dir}" status --porcelain)" ]] ||
  [[ "$(<"${release_dir}/LATEST")" != "${release}" ]]
then
  echo "error: cached candidate is not the clean exact release ${release}" >&2
  exit 1
fi

command=(
  python3
  "${release_dir}/platform/update/reconcile.py"
  --release "${release}"
  --candidate "${release_dir}"
  --mode "${mode}"
)
if [[ "${approved}" == true ]]; then
  command+=(--approved)
fi
if [[ -n "${owner_name}" ]]; then
  command+=(--owner-name "${owner_name}")
fi
"${command[@]}"
