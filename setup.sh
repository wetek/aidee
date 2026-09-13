#!/usr/bin/env bash
set -Eeuo pipefail

AIDEE_RELEASE="v0.1.0-alpha.7"
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
daily_update_check="$(
  python3 "${plan_tool}" "${stored_plan}" --get updates.daily_check
)"
telegram_access=""
telegram_menu_button="false"
if [[ "${messaging}" == *'"telegram"'* ]]; then
  telegram_access="$(
    python3 "${plan_tool}" "${stored_plan}" --get controller.telegram.access
  )"
  telegram_menu_button="$(
    python3 "${plan_tool}" "${stored_plan}" --get controller.telegram.menu_button
  )"
fi

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
      cat > "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}" <<EOF
${AIDEE_CONTROLLER_USER} ALL=(ALL) NOPASSWD: ALL
EOF
      chmod 0440 "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}"
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
      jq -n --arg name "${owner_name}" '{name: $name}' \
        > /etc/aidee/owner.json
      chmod 0644 /etc/aidee/owner.json
      set_phase "install_controller"
      ;;

    install_controller)
      step "Install the pinned Hermes controller"
      cat > "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}" <<EOF
${AIDEE_CONTROLLER_USER} ALL=(ALL) NOPASSWD: ALL
EOF
      chmod 0440 "/etc/sudoers.d/${AIDEE_CONTROLLER_USER}"
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
          dashboard_url="$(
            tailscale status --json |
              python3 -c 'import json,sys; print("https://" + json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))'
          )"
          ;;
        ssh_tunnel)
          step "Use temporary SSH tunnel access"
          echo "Keep the dashboard bound to 127.0.0.1:9119."
          echo "Use an SSH local port forward from your administration device."
          dashboard_url="http://127.0.0.1:9119"
          ;;
        *)
          fail "Unsupported dashboard access method: ${dashboard_access}"
          ;;
      esac
      dashboard_url_file="${AIDEE_STATE_DIR}/fleet/controller/DASHBOARD_URL"
      printf '%s\n' "${dashboard_url}" > "${dashboard_url_file}"
      chown "${AIDEE_CONTROLLER_USER}:${AIDEE_CONTROLLER_USER}" \
        "${dashboard_url_file}"
      chmod 0640 "${dashboard_url_file}"
      set_phase "install_admin_helper"
      ;;

    install_admin_helper)
      step "Install the narrow administration helper"
      /opt/aidee/source/platform/scripts/install-admin-helper.sh
      set_phase "build_shared_image"
      ;;

    build_shared_image)
      step "Build the shared assistant image"
      /opt/aidee/source/platform/scripts/build-assistant-image.sh
      /opt/aidee/source/platform/scripts/validate-assistant-image.sh
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
      if [[ "${telegram_access}" == "allowlist" ]] &&
        ! grep -Eq '^TELEGRAM_ALLOWED_USERS=.+$' "${controller_home}/.hermes/.env"
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
        if [[ -n "${telegram_access}" ]]; then
          echo "  Telegram access: ${telegram_access}"
        fi
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
      step "Prepare controller first-run onboarding"
      controller_state="${AIDEE_STATE_DIR}/fleet/controller"
      avatar_directory="${AIDEE_STATE_DIR}/controller-home/.hermes/onboarding"
      install -d \
        -m 0750 \
        -o "${AIDEE_CONTROLLER_USER}" \
        -g "${AIDEE_CONTROLLER_USER}" \
        "${avatar_directory}"
      summary="${controller_state}/SETUP_SUMMARY.md"
      dashboard_url="$(<"${controller_state}/DASHBOARD_URL")"
      python3 "${plan_tool}" "${stored_plan}" --summary > "${summary}"
      {
        echo
        echo "Dashboard URL: ${dashboard_url}"
        echo "Installed release: ${AIDEE_RELEASE}"
      } >> "${summary}"

      telegram_profile_status="pending"
      telegram_owner_authorized="false"
      update_check_status="pending"
      if [[ "${messaging}" != *'"telegram"'* ]]; then
        telegram_profile_status="skipped"
        telegram_owner_authorized="true"
      fi
      if [[ "${daily_update_check}" != "true" ]]; then
        update_check_status="disabled"
      fi
      onboarding_status="${controller_state}/CONTROLLER_ONBOARDING_STATUS.json"
      cat > "${onboarding_status}" <<EOF
{
  "telegram_owner_authorized": ${telegram_owner_authorized},
  "telegram_profile_status": "${telegram_profile_status}",
  "update_check_status": "${update_check_status}",
  "dashboard_verified": false
}
EOF

      controller_cron_args=(--approved --status-file "${onboarding_status}")
      if [[ "${daily_update_check}" != "true" ]]; then
        controller_cron_args+=(--skip-update-check)
      fi
      runuser -u "${AIDEE_CONTROLLER_USER}" -- \
        env HOME="${controller_home}" PATH="${controller_home}/.local/bin:${PATH}" \
        python3 /opt/aidee/source/platform/controller-tools/install-default-crons.py \
          "${controller_cron_args[@]}"

      onboarding="${controller_state}/CONTROLLER_ONBOARDING.md"
      cat > "${onboarding}" <<EOF
# Controller first-run onboarding

Complete this before project or assistant work.

Dashboard URL: ${dashboard_url}
Dashboard menu button: ${telegram_menu_button}
Telegram access: ${telegram_access:-not selected}
Daily update check: ${daily_update_check}

1. Read SETUP_SUMMARY.md and confirm it matches the owner's choices.
2. Pair or allowlist the owner before accepting operational requests.
3. Ask the owner to run /whoami in Telegram and confirm authorized access.
4. Run /opt/aidee/source/platform/controller-tools/mark-telegram-authorized.py.
5. Set this chat as home channel (/sethome). Confirm default update check and watchdog crons are active.
6. Offer to set up the Telegram bot profile now, later, or not at all.
7. If the owner chooses later or skip, record it with set-telegram-profile-status.py.
8. If the owner chooses now, draft the name, descriptions, commands, and avatar.
9. Detect whether an image-generation tool is available.
10. If available, ask the owner for an avatar style and generate options.
11. Otherwise, ask the owner to upload a static JPG avatar.
12. Write the approved profile to TELEGRAM_PROFILE.json.
13. Apply and verify it with update-telegram-profile.py.
14. Add the dashboard URL as the Telegram menu button when enabled.
15. Ask the owner to open the dashboard from their phone using the phone steps below.
16. After the owner confirms it works, run mark-dashboard-verified.py.
17. Report the branding choice, update check, and verified dashboard URL.

## Phone access

Give these steps when the dashboard URL is an https://<device>.<tailnet>.ts.net address. Do not send host install commands.

1. Install the Tailscale app on your phone.
2. Sign in with the same email you used to approve this server.
3. Turn the Tailscale VPN on. Wait until the app shows connected.
4. Open the dashboard from the Telegram bot menu button.
5. If the dashboard asks you to sign in, use the dashboard username and password from host setup.
EOF

      chown "${AIDEE_CONTROLLER_USER}:${AIDEE_CONTROLLER_USER}" \
        "${summary}" "${onboarding_status}" "${onboarding}"
      chmod 0640 "${summary}" "${onboarding_status}" "${onboarding}"
      set_phase "awaiting_controller_onboarding"
      ;;

    awaiting_controller_onboarding)
      step "Complete controller first-run onboarding"
      controller_state="${AIDEE_STATE_DIR}/fleet/controller"
      onboarding_status="${controller_state}/CONTROLLER_ONBOARDING_STATUS.json"
      if ! python3 \
        /opt/aidee/source/platform/setup/onboarding.py \
        "${onboarding_status}"
      then
        if [[ "${telegram_access}" == "pairing" ]]; then
          echo "Telegram pairing:"
          echo "  1. Message the controller bot."
          echo "  2. Open the private dashboard's Pairing page."
          echo "  3. Approve the pending Telegram pairing."
          echo "  4. Send /whoami to confirm access."
          echo
        fi
        echo "Send this to the controller through Telegram or dashboard chat:"
        echo
        echo "  Read ${controller_state}/CONTROLLER_ONBOARDING.md and complete it."
        echo
        echo "After controller onboarding and phone dashboard access are verified, run:"
        echo "  sudo ./setup.sh"
        exit 0
      fi
      set_phase "complete"
      ;;

    complete)
      step "Controller setup complete"
      python3 "${plan_tool}" "${stored_plan}" --summary
      echo
      echo "Assistant provisioning is not automated in this alpha."
      exit 0
      ;;

    *)
      fail "Unknown setup phase: ${phase}"
      ;;
  esac
done
