---
name: controller-feedback
description: Offers to share owner-approved Aidee bugs, feature requests, docs gaps, and insights as a GitHub issue. Use when the owner hits a product finding during controller work, or asks to send feedback to Aidee developers.
---

# Controller feedback

Offer to share a finding with Aidee developers. The owner decides. Share nothing unless they ask.

## When to offer

Offer once, at a pause, when the owner hits:

- A bug or unexpected Aidee behavior
- A missing feature they needed
- A docs or setup gap
- A useful insight about the product

Do not offer during onboarding or an in-progress update unless the finding is the current topic.
Do not offer for ordinary how-to questions.
If they decline or ignore the offer, drop it. Do not ask again for the same finding.

## Security

If the finding is a vulnerability or leaked credential, stop. Follow `SECURITY.md`. Do not draft a public issue.

Never include tokens, passwords, private keys, private repository URLs, owner identity, or host identifiers unless the owner writes them into the draft on purpose.

## Ask first

Ask one short question. Example:

This looks useful for Aidee maintainers. Want a draft GitHub issue you can submit? Reply yes or no.

Wait for a clear yes.

## Draft

Collect:

- Kind: `bug`, `feature`, `docs`, or `insight`
- Title
- What happened
- What they expected, or the improvement
- Host release from `git -C /opt/aidee/source describe --tags --exact-match`
- Knowledge release from `$HOME/.hermes/aidee-upstream/SYNCED_RELEASE` when present
- Channel if known, such as Telegram

Show the draft. Wait for approval.

## Build the submit link

Write the approved body to a temp file, then run:

~~~bash
/opt/aidee/source/platform/controller-tools/draft-feedback-issue.py \
  --title "Short title" \
  --kind bug \
  --body-file /tmp/aidee-feedback.md \
  --host-release "HOST_RELEASE" \
  --knowledge-release "KNOWLEDGE_RELEASE" \
  --channel telegram
~~~

Omit release or channel flags when the value is unknown.

If the tool reports a secret, remove it and rerun. Do not send the owner a rejected draft.

Send the printed URL. Tell them to open it, review, and submit. Aidee does not file the issue for them.

If they have no GitHub account, they can skip it.
