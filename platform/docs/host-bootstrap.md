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

## Setup interface

The owner calls one setup program. They do not call the internal installers separately.

Start with an approved non-secret plan:

~~~bash
sudo ./setup.sh --plan setup-plan.json
~~~

Resume after a reboot or manual authorization:

~~~bash
sudo ./setup.sh
~~~

Inspect progress:

~~~bash
sudo ./setup.sh --status
~~~

`setup.sh` validates the plan before changing the host. It stores the plan and current phase under `/var/lib/aidee/setup`.

## Internal sequence

The setup program calls internal scripts in this order:

1. `preflight-host.sh`
2. `bootstrap-host.sh`
3. `verify-host.sh`
4. `init-fleet.sh`
5. `install-controller.sh`
6. `install-controller-service.sh`
7. `install-tailscale.sh` when selected
8. `install-controller-gateway.sh` after credentials are configured

If one step fails, rerun `sudo ./setup.sh` after correcting the reported problem. Do not skip phases or call later scripts to bypass a failed check.

The public bootstrap block lives in `docs/setup.md`. Do not publish an alternate root script path or a downloaded-script pipe.

## Provider-specific security

Aidee does not automate provider firewalls in the host bootstrap. Before entering credentials:

1. Use SSH keys and disable password login.
2. Restrict SSH by source address or the provider's private access product where practical.
3. Keep dashboard and API ports closed publicly.
4. Confirm that an SSH tunnel can reach a loopback-bound dashboard.

Provider guides may explain the relevant controls, but the setup agent must confirm each account-level or firewall change before applying it.
