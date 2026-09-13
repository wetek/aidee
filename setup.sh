#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_RELEASE="v0.1.0-alpha.2"
AIDEE_REPOSITORY="https://github.com/wetek/aidee.git"
AIDEE_CONTROLLER_USER="${AIDEE_CONTROLLER_USER:-aidee-controller}"
AIDEE_STATE_DIR="${AIDEE_STATE_DIR:-/var/lib/aidee}"
AIDEE_SETUP_DIR="${AIDEE_SETUP_DIR:-${AIDEE_STATE_DIR}/setup}"

source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plan_tool="${source_root}/platform/setup/plan.py"
provided_plan=""
check_plan=false
show_status=false

usage() {
  cat <<'EOF'
Usage:
  sudo ./setup.sh --plan setup-plan.json
  sudo ./setup.sh
  ./setup.sh --check-plan setup-plan.json
  sudo ./setup.sh --status

The first command starts setup. Run `sudo ./setup.sh` again after a reboot
or a manual credential step. Progress is stored under /var/lib/aidee/setup.
EOF
}

fail() {
  echo "Aidee setup paused"
  echo
  echo "Error: $*" >&2
  exit 1
}

step() {
  echo
  echo "Aidee install [${phase}]"
  echo "$1"
  echo
}

while (( $# > 0 )); do
  case "$1" in
    --plan)
      provided_plan="${2:-}"
      shift 2
      ;;
    --check-plan)
      check_plan=true
      provided_plan="${2:-}"
      shift 2
      ;;
    --status)
      show_status=true
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

if [[ ! -x "${plan_tool}" ]]; then
  fail "Plan validator not found: ${plan_tool}"
fi

if [[ "${check_plan}" == true ]]; then
  [[ -n "${provided_plan}" ]] || fail "--check-plan requires a file"
  exec python3 "${plan_tool}" "${provided_plan}"
fi

if [[ "${EUID}" -ne 0 ]]; then
  fail "Run setup with sudo."
fi

install -d -m 0700 -o root -g root "${AIDEE_SETUP_DIR}"
state_file="${AIDEE_SETUP_DIR}/phase"
stored_plan="${AIDEE_SETUP_DIR}/setup-plan.json"
boot_id_file="${AIDEE_SETUP_DIR}/boot-id-before-reboot"

if [[ -f "${state_file}" ]]; then
  phase="$(<"${state_file}")"
else
  phase="new"
fi

if [[ "${show_status}" == true ]]; then
  echo "Aidee setup phase: ${phase}"
  if [[ -f "${stored_plan}" ]]; then
    python3 "${plan_tool}" "${stored_plan}" --summary
  fi
  exit 0
fi

set_phase() {
  local next_phase="$1"
  local temporary="${state_file}.tmp"
  printf '%s\n' "${next_phase}" > "${temporary}"
  chmod 0600 "${temporary}"
  mv "${temporary}" "${state_file}"
  phase="${next_phase}"
}

if [[ -n "${provided_plan}" ]]; then
  python3 "${plan_tool}" "${provided_plan}" >/dev/null
  if [[ -f "${stored_plan}" ]] && ! cmp -s "${provided_plan}" "${stored_plan}"; then
    fail "A different setup plan is already in progress."
  fi
  install -m 0600 -o root -g root "${provided_plan}" "${stored_plan}"
fi

if [[ ! -f "${stored_plan}" ]]; then
  fail "Start with --plan setup-plan.json."
fi

python3 "${plan_tool}" "${stored_plan}" >/dev/null
plan_release="$(python3 "${plan_tool}" "${stored_plan}" --get release)"
if [[ "${plan_release}" != "${AIDEE_RELEASE}" ]]; then
  fail "The plan release does not match this installer."
fi

owner_name="$(python3 "${plan_tool}" "${stored_plan}" --get owner.name)"
dashboard_access="$(
  python3 "${plan_tool}" "${stored_plan}" --get server.dashboard_access
)"
messaging="$(
  python3 "${plan_tool}" "${stored_plan}" --get controller.messaging
)"

while true; do
  case "${phase}" in
    new)
      step "Validate the approved plan and host"
      python3 "${plan_tool}" "${stored_plan}" --summary
      "${source_root}/platform/scripts/preflight-host.sh"
      set_phase "host_bootstrap"
      ;;

    host_bootstrap)
      step "Install host packages and Docker"
      "${source_root}/platform/scripts/bootstrap-host.sh"
      cat /proc/sys/kernel/random/boot_id > "${boot_id_file}"
      chmod 0600 "${boot_id_file}"
      set_phase "awaiting_reboot"
      echo
      echo "A reboot is required."
      echo
      echo "Run:"
      echo "  sudo reboot"
      echo
      echo "Reconnect, return to ${source_root}, then run:"
      echo "  sudo ./setup.sh"
      exit 0
      ;;

    awaiting_reboot)
      previous_boot_id="$(<"${boot_id_file}")"
      current_boot_id="$(< /proc/sys/kernel/random/boot_id)"
      if [[ "${previous_boot_id}" == "${current_boot_id}" ]]; then
        fail "Reboot the server, reconnect, and run sudo ./setup.sh again."
      fi
      set_phase "install_source"
      ;;

    install_source)
      step "Install the pinned Aidee source"
      if [[ ! -d /opt/aidee/source/.git ]]; then
        git clone \
          --branch "${AIDEE_RELEASE}" \
          --depth 1 \
          "${AIDEE_REPOSITORY}" \
          /opt/aidee/source
      fi
      installed_release="$(
        git -C /opt/aidee/source describe --tags --exact-match 2>/dev/null || true
      )"
      if [[ "${installed_release}" != "${AIDEE_RELEASE}" ]]; then
        fail "/opt/aidee/source is not checked out at ${AIDEE_RELEASE}."
      fi
      set_phase "verify_host"
      ;;

    verify_host)
      step "Verify the bootstrapped host"
      /opt/aidee/source/platform/scripts/verify-host.sh
      set_phase "initialize_fleet"
      ;;

    initialize_fleet)
      step "Create private fleet state"
      if [[ ! -f "${AIDEE_STATE_DIR}/fleet/registry.yaml" ]]; then
        runuser -u "${AIDEE_CONTROLLER_USER}" -- \
          /opt/aidee/source/platform/scripts/init-fleet.sh \
          --owner-name "${owner_name}" \
          --repository-url "${AIDEE_REPOSITORY}"
      fi
      set_phase "install_controller"
      ;;

    install_controller)
      step "Install the pinned Hermes controller"
      controller_home="$(
        getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6
      )"
      if [[ ! -x "${controller_home}/.local/bin/hermes" ]]; then
        /opt/aidee/source/platform/scripts/install-controller.sh
      fi
      set_phase "install_dashboard"
      ;;

    install_dashboard)
      step "Start the private controller dashboard"
      /opt/aidee/source/platform/scripts/install-controller-service.sh
      set_phase "configure_access"
      ;;

    configure_access)
      case "${dashboard_access}" in
        tailscale)
          step "Connect private phone access"
          if ! command -v tailscale >/dev/null 2>&1; then
            /opt/aidee/source/platform/scripts/install-tailscale.sh
          fi
          if ! tailscale status --json 2>/dev/null |
            python3 -c 'import json,sys; raise SystemExit(json.load(sys.stdin).get("BackendState") != "Running")'
          then
            echo "Tailscale will show a private authorization URL."
            echo "Open it yourself. Do not paste it into chat."
            tailscale up
          fi
          tailscale serve --bg 9119
          tailscale serve status
          ;;
        ssh_tunnel)
          step "Use temporary SSH tunnel access"
          echo "Keep the dashboard bound to 127.0.0.1:9119."
          echo "Use an SSH local port forward from your administration device."
          ;;
        *)
          fail "Unsupported dashboard access method: ${dashboard_access}"
          ;;
      esac
      set_phase "awaiting_credentials"
      ;;

    awaiting_credentials)
      step "Configure the controller"
      controller_home="$(
        getent passwd "${AIDEE_CONTROLLER_USER}" | cut -d: -f6
      )"
      hermes="${controller_home}/.local/bin/hermes"
      configured_model="$(
        runuser -u "${AIDEE_CONTROLLER_USER}" -- \
          env HOME="${controller_home}" \
          "${hermes}" config get model 2>/dev/null || true
      )"
      credentials_ready=true
      if [[ -z "${configured_model//[[:space:]]/}" ]]; then
        credentials_ready=false
      fi
      if [[ "${messaging}" == *'"telegram"'* ]] &&
        ! grep -Eq '^TELEGRAM_BOT_TOKEN=.+$' "${controller_home}/.hermes/.env"
      then
        credentials_ready=false
      fi
      if [[ "${messaging}" == *'"discord"'* ]] &&
        ! grep -Eq '^DISCORD_BOT_TOKEN=.+$' "${controller_home}/.hermes/.env"
      then
        credentials_ready=false
      fi
      if [[ "${messaging}" == *'"slack"'* ]] &&
        ! grep -Eq '^SLACK_BOT_TOKEN=.+$' "${controller_home}/.hermes/.env"
      then
        credentials_ready=false
      fi
      if [[ "${messaging}" == *'"slack"'* ]] &&
        ! grep -Eq '^SLACK_APP_TOKEN=.+$' "${controller_home}/.hermes/.env"
      then
        credentials_ready=false
      fi

      if [[ "${credentials_ready}" != true ]]; then
        echo "Open the private dashboard and configure:"
        echo "  Model provider: $(
          python3 "${plan_tool}" "${stored_plan}" --get controller.model_provider
        )"
        echo "  Messaging: ${messaging}"
        echo
        echo "Create third-party credentials yourself and enter them in the dashboard."
        echo "Never paste credentials into chat."
        echo
        echo "When configuration is complete, run:"
        echo "  sudo ./setup.sh"
        exit 0
      fi
      set_phase "start_gateway"
      ;;

    start_gateway)
      step "Start and verify messaging"
      /opt/aidee/source/platform/scripts/install-controller-gateway.sh
      set_phase "write_handoff"
      ;;

    write_handoff)
      step "Write the non-secret controller handoff"
      summary="${AIDEE_STATE_DIR}/fleet/controller/SETUP_SUMMARY.md"
      python3 "${plan_tool}" "${stored_plan}" --summary > "${summary}"
      chown "${AIDEE_CONTROLLER_USER}:${AIDEE_CONTROLLER_USER}" "${summary}"
      chmod 0640 "${summary}"
      set_phase "complete"
      ;;

    complete)
      step "Setup complete"
      python3 "${plan_tool}" "${stored_plan}" --summary
      echo
      echo "In the controller Telegram chat, send:"
      echo "  Read SETUP_SUMMARY.md, confirm the setup record, and update durable memory."
      echo
      echo "Assistant provisioning is not automated in this alpha."
      exit 0
      ;;

    *)
      fail "Unknown setup phase: ${phase}"
      ;;
  esac
done
