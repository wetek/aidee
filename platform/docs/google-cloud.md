# Google Cloud

This guide covers a small Aidee pilot on Google Compute Engine. Google Cloud is one supported host provider, not an Aidee dependency.

## Suggested VM

- A region near the owner and any required data boundary.
- Standard provisioning instead of Spot.
- General-purpose E2 machine.
- `e2-standard-2` or larger for coding work.
- Ubuntu 24.04 or 26.04 LTS on x86-64.
- At least 80 GB of balanced persistent disk.
- No attached Google Cloud service account unless an assistant needs a specific Google API.
- HTTP and HTTPS firewall options disabled.
- OS Login enabled.
- Secure Boot, vTPM, integrity monitoring, and deletion protection enabled.

Do not select "Deploy container." Aidee installs Docker and manages its own containers.

## First connection

1. Create the VM.
2. Record its project, name, zone, external address, and SSH user in a private operator record.
3. Connect over SSH.
4. Run the Aidee host preflight.
5. Do not enter model, Telegram, Git, or MCP credentials yet.

Provider browser consoles can corrupt pasted punctuation. Use a normal SSH client or `gcloud compute ssh` for installation commands.

## Restrict SSH

A default Google Cloud SSH firewall rule may expose port 22 broadly. Before adding credentials, use Identity-Aware Proxy TCP forwarding or restrict the rule to trusted source addresses. Confirm that access still works before closing the original route.

Never commit a project ID, live IP address, SSH user, or private key to the public Aidee repository.
