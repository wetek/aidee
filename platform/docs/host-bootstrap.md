# Host bootstrap

The first Aidee pilot supports dedicated amd64 VPS instances running Ubuntu 24.04 or 26.04.

## What the bootstrap does

- Updates installed operating-system packages.
- Installs Git, Docker Engine, Docker Compose, and basic administration tools.
- Creates the unprivileged `aidee-controller` account.
- Creates root-owned code and configuration directories.
- Creates private state, secret, runtime, and backup directories.
- Enables unattended security updates.

The controller does not receive sudo access or Docker group membership. A later installation step adds a root-owned administration helper with a narrow command set.

## Run from a reviewed revision

Do not pipe a remote script into a shell.

~~~bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/wetek/aidee.git
cd aidee
git checkout PINNED_VERSION_OR_COMMIT
./platform/scripts/preflight-host.sh
sudo ./platform/scripts/bootstrap-host.sh
sudo systemctl reboot
~~~

Reconnect through the protected SSH path after the host restarts. Install the selected Aidee revision into the root-owned code directory:

~~~bash
sudo git clone https://github.com/wetek/aidee.git /opt/aidee/source
sudo git -C /opt/aidee/source checkout PINNED_VERSION_OR_COMMIT
/opt/aidee/source/platform/scripts/verify-host.sh
sudo -u aidee-controller /opt/aidee/source/platform/scripts/init-fleet.sh \
  --owner-name "OWNER_NAME" \
  --repository-url "https://github.com/wetek/aidee.git"
sudo /opt/aidee/source/platform/scripts/install-controller.sh
sudo /opt/aidee/source/platform/scripts/install-controller-service.sh
~~~

Replace `OWNER_NAME` and `PINNED_VERSION_OR_COMMIT` with the values selected in the approved setup plan.

For private phone access, continue with [the Tailscale guide](tailscale.md). After model and messaging credentials are configured through the protected dashboard, run:

~~~bash
sudo /opt/aidee/source/platform/scripts/install-controller-gateway.sh
~~~

## Provider-specific security

Aidee does not automate provider firewalls in the host bootstrap. Before entering credentials:

1. Use SSH keys and disable password login.
2. Restrict SSH by source address or the provider's private access product where practical.
3. Keep dashboard and API ports closed publicly.
4. Confirm that an SSH tunnel can reach a loopback-bound dashboard.

Provider guides may explain the relevant controls, but the setup agent must confirm each account-level or firewall change before applying it.
