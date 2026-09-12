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

## Command ownership

- Ubuntu Apt installs Git before Aidee can be cloned.
- `bootstrap-host.sh` installs system packages and Docker. It creates the controller account and Aidee directories.
- `install-controller.sh` installs pinned Hermes, Python, Node.js, and the dashboard frontend.
- `install-controller-service.sh` starts the loopback-bound dashboard.
- `install-tailscale.sh` installs Tailscale when the owner selected private phone access.
- `install-controller-gateway.sh` starts messaging after the owner configures credentials.

The host bootstrap does not install Node.js, Hermes, Tailscale, messaging credentials, or assistants.

## Canonical commands

This page is the only source for host installation commands. Do not move, shorten, combine, or reconstruct them. Stop if this page cannot be loaded.

Do not pipe downloaded code into a shell.

~~~bash
sudo apt-get update
sudo apt-get install -y git
git clone --branch v0.1.0-alpha.1 --depth 1 https://github.com/wetek/aidee.git
cd aidee
./platform/scripts/preflight-host.sh
sudo ./platform/scripts/bootstrap-host.sh
sudo systemctl reboot
~~~

Reconnect through the protected SSH path after the host restarts. Install the selected Aidee revision into the root-owned code directory:

~~~bash
sudo git clone \
  --branch v0.1.0-alpha.1 \
  --depth 1 \
  https://github.com/wetek/aidee.git \
  /opt/aidee/source
/opt/aidee/source/platform/scripts/verify-host.sh
sudo -u aidee-controller /opt/aidee/source/platform/scripts/init-fleet.sh \
  --owner-name "OWNER_NAME" \
  --repository-url "https://github.com/wetek/aidee.git"
sudo /opt/aidee/source/platform/scripts/install-controller.sh
sudo /opt/aidee/source/platform/scripts/install-controller-service.sh
~~~

Replace only `OWNER_NAME` with the owner name confirmed in the approved setup plan.

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
