# Shared assistant image

Aidee builds one assistant image per release and reuses its immutable image ID for every assistant on that host.

The image derives from the official Hermes `v2026.9.11` image by digest. Hermes already provides Python, uv, Node.js, npm, npx, Git, SSH, curl, ripgrep, ffmpeg, compiler tools, Playwright, messaging dependencies, and MCP runtimes.

Aidee adds:

- GitHub CLI.
- jq.
- socat for loopback dashboard forwarding.
- OpenCode 1.18.3.
- Versioned Aidee skills, instructions, workflows, and defaults.

The image contains no assistant identity, memory, repository, or credential.

Build and validate:

~~~bash
sudo /opt/aidee/source/platform/scripts/build-assistant-image.sh
sudo /opt/aidee/source/platform/scripts/validate-assistant-image.sh
~~~

The scripts write the approved image record under `/etc/aidee/images`. Assistant provisioning accepts only the recorded image ID.

Separate assistants share read-only image layers. They do not share containers, writable Hermes homes, credentials, repositories, memory, or resource limits.
