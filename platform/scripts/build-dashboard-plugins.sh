#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
plugins_dir="${root}/platform/dashboard-plugins"

if ! command -v npx >/dev/null 2>&1; then
  echo "error: npx is required to build dashboard plugins" >&2
  exit 1
fi

build_plugin() {
  local name="$1"
  local source="${plugins_dir}/${name}/dashboard/src/index.tsx"
  local output="${plugins_dir}/${name}/dashboard/dist/index.js"
  if [[ ! -f "${source}" ]]; then
    echo "error: plugin source is missing: ${source}" >&2
    exit 1
  fi
  mkdir -p "$(dirname -- "${output}")"
  npx --yes esbuild@0.25.9 \
    "${source}" \
    --bundle \
    --format=iife \
    --outfile="${output}" \
    --jsx=transform \
    --jsx-factory=React.createElement \
    --jsx-fragment=React.Fragment \
    --legal-comments=none
}

build_plugin "aidee-overview"
build_plugin "aidee-assistant-home"

echo "Aidee dashboard plugins built."
