#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run with sudo on the Aidee host" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_dir}/../.." && pwd)"
version="$(<"${repository_root}/LATEST")"
record="/etc/aidee/images/${version}.json"

if [[ ! -f "${record}" ]]; then
  echo "error: image record not found: ${record}" >&2
  exit 1
fi

image_id="$(jq -r '.image_id' "${record}")"
recorded_commit="$(jq -r '.source_commit' "${record}")"
source_commit="$(git -C "${repository_root}" rev-parse HEAD)"
expected_hermes_version="$(<"${repository_root}/platform/HERMES_VERSION")"
if [[ "${recorded_commit}" != "${source_commit}" ]]; then
  echo "error: image record does not match the checked-out source" >&2
  exit 1
fi

actual_version="$(
  docker image inspect "${image_id}" \
    --format '{{index .Config.Labels "org.opencontainers.image.version"}}'
)"
if [[ "${actual_version}" != "${version}" ]]; then
  echo "error: image version label mismatch" >&2
  exit 1
fi
actual_revision="$(
  docker image inspect "${image_id}" \
    --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
)"
actual_hermes_version="$(
  docker image inspect "${image_id}" \
    --format '{{index .Config.Labels "io.aidee.hermes.version"}}'
)"
if [[ "${actual_revision}" != "${source_commit}" ]]; then
  echo "error: image source revision label mismatch" >&2
  exit 1
fi
if [[ "${actual_hermes_version}" != "${expected_hermes_version}" ]]; then
  echo "error: image Hermes version label mismatch" >&2
  exit 1
fi

docker run \
  --rm \
  --read-only \
  --security-opt no-new-privileges:true \
  --tmpfs /run:rw,exec,nosuid,nodev,size=64m \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m \
  "${image_id}" \
  sh -c '
    test "$(id -u hermes)" = "10000"
    hermes --version
    opencode --version
    gh --version
    jq --version
    socat -V
  '

test_root="$(mktemp -d /var/lib/aidee/runtime/image-test.XXXXXX)"
container_a="aidee-image-test-a-$$"
container_b="aidee-image-test-b-$$"
cleanup() {
  docker rm -f "${container_a}" "${container_b}" >/dev/null 2>&1 || true
  rm -rf "${test_root}"
}
trap cleanup EXIT

mkdir -p "${test_root}/a" "${test_root}/b"
touch "${test_root}/a/sentinel-a"

for entry in "a:${container_a}" "b:${container_b}"; do
  data_dir="${test_root}/${entry%%:*}"
  container="${entry#*:}"
  docker create \
    --name "${container}" \
    --cpus 0.5 \
    --memory 1024m \
    --pids-limit 128 \
    --read-only \
    --security-opt no-new-privileges:true \
    --tmpfs /run:rw,exec,nosuid,nodev,size=64m \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m \
    --volume "${data_dir}:/opt/data" \
    "${image_id}" \
    sleep infinity >/dev/null
  docker start "${container}" >/dev/null
done

image_a="$(docker inspect "${container_a}" --format '{{.Image}}')"
image_b="$(docker inspect "${container_b}" --format '{{.Image}}')"
[[ "${image_a}" == "${image_id}" && "${image_b}" == "${image_id}" ]]

docker exec --user 10000:10000 "${container_a}" test -f /opt/data/sentinel-a
if docker exec --user 10000:10000 "${container_b}" test -e /opt/data/sentinel-a; then
  echo "error: assistant B can see assistant A state" >&2
  exit 1
fi

for container in "${container_a}" "${container_b}"; do
  [[ "$(docker inspect "${container}" --format '{{.HostConfig.ReadonlyRootfs}}')" == "true" ]]
  [[ "$(docker inspect "${container}" --format '{{.HostConfig.Memory}}')" == "1073741824" ]]
  [[ "$(docker inspect "${container}" --format '{{.HostConfig.NanoCpus}}')" == "500000000" ]]
  [[ "$(docker inspect "${container}" --format '{{.HostConfig.PidsLimit}}')" == "128" ]]
  if docker inspect "${container}" --format '{{json .Mounts}}' | grep -q 'docker.sock'; then
    echo "error: Docker socket is mounted in ${container}" >&2
    exit 1
  fi
done

docker rm -f "${container_a}" >/dev/null
[[ "$(docker inspect "${container_b}" --format '{{.State.Running}}')" == "true" ]]
docker image inspect "${image_id}" >/dev/null

temporary="${record}.tmp"
jq '.validation = "validated"' "${record}" > "${temporary}"
chmod 0644 "${temporary}"
mv "${temporary}" "${record}"

echo "Aidee assistant image validated: ${image_id}"
