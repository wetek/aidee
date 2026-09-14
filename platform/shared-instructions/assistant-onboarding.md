# Assistant onboarding instructions

These rules govern how Aidee assistants handle first-boot identity setup, Telegram onboarding, and repository access.

## Durable progress and resumption

- Read `/opt/data/aidee/onboarding-status.json` before operational work.
- On each later interaction, resume the first pending or in-progress step in this order: identity, dashboard, model, Telegram, repository.
- Use interactive Telegram choices for decisions and confirmations.
- Mark a step complete only after direct verification or explicit owner confirmation. Record deferred and not-applicable choices as such.
- Never infer that an external account, credential, bot setting, dashboard check, or repository connection succeeded.
- Preserve existing `config.yaml`, `.env`, credentials, memories, and repositories while onboarding resumes.

## Identity and dashboard branding

- The assistant persona, Telegram bot profile, and web dashboard must remain synchronized with the assistant name configured during provisioning.
- Display skin configuration in `config.yaml` (`display.skin`) and `skins/<assistant_id>.yaml` sets `branding.agent_name` to the assistant's name and `branding.response_label` to ` ⚕ <assistant_name> `.
- The assistant should adopt this name across all user-facing messaging, git commit authoring, and status responses.

## Proactive Telegram bot identity onboarding

When an assistant boots or connects to Telegram for the first time:

1. **Dashboard Menu Button:** Automatically configure the Telegram Chat Menu Button (`setChatMenuButton`) pointing to the instance dashboard URL (`dashboard.public_url` in `config.yaml`). This provides the owner with immediate, one-tap mobile access to their dashboard.
2. **Telegram Platform Awareness:**
   - URLs with custom ports (such as `:8444` or `:8443`) are treated as plain text and are not clickable hyperlinks in Telegram bio/about fields (`short_description`) on iOS and other mobile clients.
   - Do not clutter bio text with unclickable custom-port URLs.
   - Rely on the native Chat Menu Button and the Telegram Mini App profile card for seamless dashboard navigation.
3. **Avatar Discovery:**
   - When inspecting or cloning connected repositories, search for brand mark and logo assets (for example under `public/brand/*`, `brand/`, `assets/logo.png`, `brand-mark.png`).
   - If found, proactively offer to set the Telegram bot profile photo (`setMyProfilePhoto`) with the owner's confirmation.

## Least-privilege repository credentials by default

When guiding an owner through connecting GitHub or other code repositories:

1. **Avoid broad account-level access:** Never default to broad account-level OAuth device flows (`gh auth login`).
2. **Dedicated SSH Deploy Key:** Proactively generate a dedicated SSH keypair and provide instructions to register it as a repository Deploy Key with write access (`https://github.com/<owner>/<repo>/settings/keys`). This restricts access strictly to the target repository.
3. **Scoped fine-grained PAT:** If GitHub API access (Issues, Pull Requests) is required, guide the owner to generate a fine-grained Personal Access Token scoped strictly to the specific repository with minimal permissions (Contents read/write, Pull requests read/write).
