#!/usr/bin/env bash
set -Eeuo pipefail

errors=0
warnings=0

pass() {
  printf 'PASS  %s\n' "$*"
}

warn() {
  printf 'WARN  %s\n' "$*"
  warnings=$((warnings + 1))
}

fail() {
  printf 'FAIL  %s\n' "$*"
  errors=$((errors + 1))
}

if [[ ! -r /etc/os-release ]]; then
  fail "Cannot read /etc/os-release."
else
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" =~ ^(24\.04|26\.04)$ ]]; then
    pass "Operating system is ${PRETTY_NAME}."
  else
    fail "Pilot requires Ubuntu 24.04 or 26.04. Found ${PRETTY_NAME:-unknown}."
  fi
fi

architecture="$(dpkg --print-architecture 2>/dev/null || uname -m)"
if [[ "${architecture}" == "amd64" || "${architecture}" == "x86_64" ]]; then
  pass "Architecture is ${architecture}."
else
  fail "Pilot requires amd64. Found ${architecture}."
fi

cpus="$(nproc)"
if (( cpus >= 2 )); then
  pass "CPU count is ${cpus}."
else
  fail "Pilot requires at least 2 CPUs. Found ${cpus}."
fi

memory_mb="$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)"
if (( memory_mb >= 7000 )); then
  pass "Usable memory is ${memory_mb} MB."
else
  fail "Pilot requires at least 7000 MB usable memory. Found ${memory_mb} MB."
fi

swap_mb="$(awk '/SwapTotal/ {print int($2 / 1024)}' /proc/meminfo)"
if (( swap_mb > 0 )); then
  pass "Swap capacity is ${swap_mb} MB."
else
  warn "No swap is configured. This is not a blocker; review it before coding workloads."
fi

disk_kb="$(df -Pk / | awk 'NR == 2 {print $4}')"
disk_gb=$((disk_kb / 1024 / 1024))
if (( disk_gb >= 50 )); then
  pass "Free root disk space is ${disk_gb} GB."
else
  fail "Pilot requires at least 50 GB free disk space. Found ${disk_gb} GB."
fi

if [[ -n "${SSH_CONNECTION:-}" ]]; then
  pass "Session is connected over SSH."
else
  warn "SSH_CONNECTION is not set. Avoid pasted commands in browser-based VPS consoles."
fi

if sudo -n true 2>/dev/null; then
  pass "Passwordless sudo is available for bootstrap."
elif command -v sudo >/dev/null 2>&1; then
  warn "Sudo is installed but requires authentication. Confirm access before bootstrap."
else
  fail "Sudo access is required for host bootstrap."
fi

if command -v docker >/dev/null 2>&1; then
  warn "Docker is already installed. Bootstrap will verify and update its packages."
else
  pass "Docker is not installed yet."
fi

if [[ -f /var/run/reboot-required ]]; then
  warn "The host already requires a reboot."
fi

echo
echo "Preflight summary: ${errors} failure(s), ${warnings} warning(s)."

if (( errors > 0 )); then
  exit 1
fi
