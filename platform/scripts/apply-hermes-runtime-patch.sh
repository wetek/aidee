#!/usr/bin/env bash
set -Eeuo pipefail

check_only=false
if [[ "${1:-}" == "--check" ]]; then
  check_only=true
  shift
fi
if (( $# != 1 )); then
  echo "usage: $0 [--check] HERMES_SOURCE" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
platform_dir="$(cd -- "${script_dir}/.." && pwd)"
source_dir="$1"
patch_file="${platform_dir}/hermes-runtime-context.patch"
base_commit="$(<"${platform_dir}/HERMES_COMMIT")"
expected_patch_sha="$(<"${platform_dir}/HERMES_PATCH_SHA256")"
checksums="${platform_dir}/HERMES_PATCHED_FILES_SHA256"
base_checksums="${platform_dir}/HERMES_BASE_FILES_SHA256"
patch_paths=(
  "--include=agent/conversation_loop.py"
  "--include=agent/system_prompt.py"
  "--include=gateway/run_agent_cache.py"
  "--include=hermes_state_sessions.py"
)

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

fail() {
  echo "error: $*" >&2
  exit 1
}

verify_checksums() {
  local manifest="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "${source_dir}" && sha256sum --check "${manifest}") >/dev/null 2>&1
  else
    (cd "${source_dir}" && shasum -a 256 --check "${manifest}") >/dev/null 2>&1
  fi
}

[[ -d "${source_dir}" ]] || fail "Hermes source directory is missing: ${source_dir}"
source_dir="$(cd -- "${source_dir}" && pwd -P)"
[[ -f "${patch_file}" && -f "${checksums}" && -f "${base_checksums}" ]] ||
  fail "Hermes patch inputs are missing"
[[ "$(sha256_file "${patch_file}")" == "${expected_patch_sha}" ]] ||
  fail "Hermes runtime patch checksum mismatch"
is_git_checkout=false
if git_root="$(git -C "${source_dir}" rev-parse --show-toplevel 2>/dev/null)"; then
  [[ "$(cd -- "${git_root}" && pwd -P)" == "${source_dir}" ]] ||
    fail "Hermes source is nested inside a different Git checkout"
  is_git_checkout=true
  [[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${base_commit}" ]] ||
    fail "Hermes source commit does not match ${base_commit}"
fi

if verify_checksums "${checksums}"; then
  already_applied=true
else
  already_applied=false
fi

if [[ "${already_applied}" == false ]]; then
  [[ "${check_only}" == false ]] ||
    fail "Hermes runtime patch is not applied"
  verify_checksums "${base_checksums}" ||
    fail "Hermes source files do not match audited base ${base_commit}"
  if [[ "${is_git_checkout}" == true ]]; then
    [[ -z "$(git -C "${source_dir}" status --porcelain --untracked-files=no)" ]] ||
      fail "Hermes source has tracked changes before patching"
  fi
  (cd "${source_dir}" && git apply "${patch_paths[@]}" --check "${patch_file}") ||
    fail "Hermes runtime patch does not apply cleanly"
  (cd "${source_dir}" && git apply "${patch_paths[@]}" "${patch_file}")
fi

if [[ "${is_git_checkout}" == true ]]; then
  expected_files="$(awk '{print $2}' "${checksums}" | LC_ALL=C sort)"
  actual_files="$(git -C "${source_dir}" diff --name-only | LC_ALL=C sort)"
  [[ "${actual_files}" == "${expected_files}" ]] ||
    fail "Hermes tracked changes do not match the audited patch file set"
fi
verify_checksums "${checksums}" ||
  fail "Hermes patched file checksum mismatch"

echo "Applied Hermes runtime patch ${expected_patch_sha} to ${base_commit}."
