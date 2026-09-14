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
expected_hermes_commit="$(<"${repository_root}/platform/HERMES_COMMIT")"
expected_hermes_patch="$(<"${repository_root}/platform/HERMES_PATCH_SHA256")"
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
actual_hermes_commit="$(
  docker image inspect "${image_id}" \
    --format '{{index .Config.Labels "io.aidee.hermes.commit"}}'
)"
actual_hermes_patch="$(
  docker image inspect "${image_id}" \
    --format '{{index .Config.Labels "io.aidee.hermes.patch-sha256"}}'
)"
if [[ "${actual_revision}" != "${source_commit}" ]]; then
  echo "error: image source revision label mismatch" >&2
  exit 1
fi
if [[ "${actual_hermes_version}" != "${expected_hermes_version}" ]]; then
  echo "error: image Hermes version label mismatch" >&2
  exit 1
fi
if [[ "${actual_hermes_commit}" != "${expected_hermes_commit}" ]] ||
  [[ "${actual_hermes_patch}" != "${expected_hermes_patch}" ]]
then
  echo "error: image Hermes patch provenance mismatch" >&2
  exit 1
fi
if [[ "$(jq -r '.hermes_commit' "${record}")" != "${expected_hermes_commit}" ]] ||
  [[ "$(jq -r '.hermes_patch_sha256' "${record}")" != "${expected_hermes_patch}" ]]
then
  echo "error: image record Hermes patch provenance mismatch" >&2
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
    cd /opt/hermes
    sha256sum --check /opt/aidee/hermes-patch/HERMES_PATCHED_FILES_SHA256
    /opt/aidee/hermes-patch/scripts/apply-hermes-runtime-patch.sh --check /opt/hermes
    test -x /opt/aidee/onboarding/onboarding-gate.py
    test -x /opt/aidee/onboarding/mark-onboarding-step.py
    test -r /opt/aidee/onboarding/onboarding_state.py
    PYTHONPATH=/opt/aidee/onboarding python -c "
from onboarding_state import default_status
assert default_status(\"assistant\", \"coding\")[\"schema_version\"] == 2
"
    python -c "
from agent.conversation_loop import _restore_or_build_system_prompt
from agent.system_prompt import runtime_context_fingerprint
from gateway.run import GatewayRunner
from hermes_state import SessionDB
assert callable(_restore_or_build_system_prompt)
assert callable(runtime_context_fingerprint)
assert callable(GatewayRunner._extract_cache_busting_config)
assert callable(SessionDB.update_runtime_context)
"
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
chown -R 10000:10000 "${test_root}/a" "${test_root}/b"
chmod 0770 "${test_root}/a" "${test_root}/b"

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

docker exec --user 10000:10000 "${container_a}" \
  /opt/aidee/onboarding/onboarding-gate.py \
  --status-file /opt/data/aidee/onboarding-status.json \
  --role assistant \
  --assistant-kind personal \
  --mode decide >/dev/null
docker exec --user 10000:10000 "${container_a}" \
  /opt/aidee/onboarding/mark-onboarding-step.py \
  --status-file /opt/data/aidee/onboarding-status.json \
  --role assistant \
  --assistant-kind personal \
  --step identity \
  --status completed \
  --evidence-source verified_tool \
  --evidence-detail "identity verified during image validation" >/dev/null
[[ "$(stat -c '%u:%g:%a' "${test_root}/a/aidee/onboarding-status.json")" == \
  "10000:10000:640" ]]

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
