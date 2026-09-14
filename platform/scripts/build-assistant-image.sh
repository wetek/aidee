#!/usr/bin/env bash
set -Eeuo pipefail

rebuild=false
if [[ "${1:-}" == "--rebuild" ]]; then
  rebuild=true
  shift
fi
if (( $# > 0 )); then
  echo "error: unknown argument: $1" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo on the Aidee host" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_dir}/../.." && pwd)"
version="$(<"${repository_root}/LATEST")"
hermes_version="$(<"${repository_root}/platform/HERMES_VERSION")"
hermes_commit="$(<"${repository_root}/platform/HERMES_COMMIT")"
hermes_patch_sha256="$(<"${repository_root}/platform/HERMES_PATCH_SHA256")"
source_commit="$(git -C "${repository_root}" rev-parse HEAD)"
tag="aidee-assistant:${version#v}-${source_commit:0:12}"
record_dir="/etc/aidee/images"
record="${record_dir}/${version}.json"

if [[ -n "$(git -C "${repository_root}" status --porcelain)" ]]; then
  echo "error: build requires a clean Aidee checkout" >&2
  exit 1
fi
source_tag="$(
  git -C "${repository_root}" describe --tags --exact-match 2>/dev/null || true
)"
if [[ "${source_tag}" != "${version}" ]]; then
  echo "error: source must be checked out at tag ${version}" >&2
  exit 1
fi

expected_label="${version}"
existing_id="$(docker image inspect "${tag}" --format '{{.Id}}' 2>/dev/null || true)"
if [[ -n "${existing_id}" && "${rebuild}" != true ]]; then
  actual_label="$(
    docker image inspect "${tag}" \
      --format '{{index .Config.Labels "org.opencontainers.image.version"}}'
  )"
  actual_revision="$(
    docker image inspect "${tag}" \
      --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  )"
  actual_hermes="$(
    docker image inspect "${tag}" \
      --format '{{index .Config.Labels "io.aidee.hermes.version"}}'
  )"
  actual_hermes_commit="$(
    docker image inspect "${tag}" \
      --format '{{index .Config.Labels "io.aidee.hermes.commit"}}'
  )"
  actual_hermes_patch="$(
    docker image inspect "${tag}" \
      --format '{{index .Config.Labels "io.aidee.hermes.patch-sha256"}}'
  )"
  if [[ "${actual_label}" != "${expected_label}" ]]; then
    echo "error: existing image has an unexpected Aidee version label" >&2
    exit 1
  fi
  if [[ "${actual_revision}" != "${source_commit}" ]]; then
    echo "error: existing image has an unexpected source revision label" >&2
    exit 1
  fi
  if [[ "${actual_hermes}" != "${hermes_version}" ]]; then
    echo "error: existing image has an unexpected Hermes version label" >&2
    exit 1
  fi
  if [[ "${actual_hermes_commit}" != "${hermes_commit}" ]] ||
    [[ "${actual_hermes_patch}" != "${hermes_patch_sha256}" ]]
  then
    echo "error: existing image has unexpected Hermes patch provenance" >&2
    exit 1
  fi
else
  docker build \
    --file "${repository_root}/platform/container/Dockerfile" \
    --build-arg "AIDEE_VERSION=${version}" \
    --build-arg "AIDEE_SOURCE_COMMIT=${source_commit}" \
    --build-arg "HERMES_VERSION=${hermes_version}" \
    --build-arg "HERMES_COMMIT=${hermes_commit}" \
    --build-arg "HERMES_PATCH_SHA256=${hermes_patch_sha256}" \
    --tag "${tag}" \
    "${repository_root}"
fi

image_id="$(docker image inspect "${tag}" --format '{{.Id}}')"
image_size="$(docker image inspect "${tag}" --format '{{.Size}}')"
hermes_version="$(
  docker image inspect "${tag}" \
    --format '{{index .Config.Labels "io.aidee.hermes.version"}}'
)"
hermes_commit="$(
  docker image inspect "${tag}" \
    --format '{{index .Config.Labels "io.aidee.hermes.commit"}}'
)"
hermes_patch_sha256="$(
  docker image inspect "${tag}" \
    --format '{{index .Config.Labels "io.aidee.hermes.patch-sha256"}}'
)"
opencode_version="$(
  docker image inspect "${tag}" \
    --format '{{index .Config.Labels "io.aidee.opencode.version"}}'
)"

install -d -m 0755 -o root -g root "${record_dir}"
temporary="${record}.tmp.$$"
trap 'rm -f "${temporary}"' EXIT
jq -n \
  --arg aidee_version "${version}" \
  --arg source_commit "${source_commit}" \
  --arg tag "${tag}" \
  --arg image_id "${image_id}" \
  --argjson image_size "${image_size}" \
  --arg hermes_version "${hermes_version}" \
  --arg hermes_commit "${hermes_commit}" \
  --arg hermes_patch_sha256 "${hermes_patch_sha256}" \
  --arg opencode_version "${opencode_version}" \
  '{
    aidee_version: $aidee_version,
    source_commit: $source_commit,
    tag: $tag,
    image_id: $image_id,
    image_size: $image_size,
    hermes_version: $hermes_version,
    hermes_commit: $hermes_commit,
    hermes_patch_sha256: $hermes_patch_sha256,
    opencode_version: $opencode_version,
    validation: "built"
  }' > "${temporary}"
chmod 0644 "${temporary}"
mv "${temporary}" "${record}"
trap - EXIT

echo "Aidee assistant image ready."
echo "Version: ${version}"
echo "Image ID: ${image_id}"
echo "Size: ${image_size} bytes"
echo "Record: ${record}"
