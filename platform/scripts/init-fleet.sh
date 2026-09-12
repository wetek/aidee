#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
target_dir="${AIDEE_STATE_DIR}/fleet"
owner_name=""
repository_url=""

usage() {
  cat <<'EOF'
Usage:
  init-fleet.sh --owner-name NAME --repository-url URL

Creates initial private Aidee fleet state. NAME and URL are not secrets.
Run this script as the aidee-controller user after host bootstrap.
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --owner-name)
      owner_name="${2:-}"
      shift 2
      ;;
    --repository-url)
      repository_url="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${owner_name}" || -z "${repository_url}" ]]; then
  usage >&2
  exit 1
fi

if [[ "${owner_name}" == *$'\n'* || ${#owner_name} -gt 100 ]]; then
  echo "error: owner name must be one line and no more than 100 characters" >&2
  exit 1
fi

if [[ "${repository_url}" == *$'\n'* || ${#repository_url} -gt 500 ]]; then
  echo "error: repository URL must be one line and no more than 500 characters" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_dir}/../.." && pwd)"
template_dir="${repository_root}/fleet-template"

if [[ ! -f "${template_dir}/registry.yaml.template" ]]; then
  echo "error: fleet template was not found at ${template_dir}" >&2
  exit 1
fi

mkdir -p "${target_dir}"
if [[ -e "${target_dir}/registry.yaml" ]]; then
  echo "error: fleet is already initialized at ${target_dir}" >&2
  exit 1
fi

cp -a "${template_dir}/." "${target_dir}/"

OWNER_NAME="${owner_name}" \
REPOSITORY_URL="${repository_url}" \
TARGET_DIR="${target_dir}" \
python3 <<'PY'
import os
from pathlib import Path

target = Path(os.environ["TARGET_DIR"])
values = {
    "{{ owner_name }}": os.environ["OWNER_NAME"],
    "{{ aidee_repository_url }}": os.environ["REPOSITORY_URL"],
}

render = [
    (target / "registry.yaml.template", target / "registry.yaml"),
    (target / "controller" / "SOUL.md.template", target / "controller" / "SOUL.md"),
]

for source, destination in render:
    text = source.read_text()
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    destination.write_text(text)
    source.unlink()

user_template = (
    target
    / "assistants"
    / "_template"
    / "memories"
    / "USER.md.template"
)
text = user_template.read_text().replace(
    "{{ owner_name }}", os.environ["OWNER_NAME"]
)
user_template.write_text(text)
PY

echo "Aidee fleet state initialized at ${target_dir}."
echo "No credentials were created or requested."
