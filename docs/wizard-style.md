# Wizard response format

Apply this format to every Aidee setup message. Also apply the [unslop skill](../platform/shared-skills/unslop/SKILL.md).

## Rules

1. Ask one question per message.
2. Show the current section and progress.
3. Keep context to two short sentences.
4. Use numbered options when the likely answers are known.
5. Put the recommended option first and mark it `(recommended)`.
6. Explain the recommendation in one sentence.
7. Always allow a custom answer.
8. Do not use tables, decorative symbols, or long introductions.
9. Do not repeat answers unless correcting or confirming them.
10. Do not show commands until the interview and plan are approved.
11. Show one action at a time during installation.
12. Wait for the result of each action before continuing.

## Interview message

Use this shape:

~~~text
Aidee setup [2/6]
Server

Do you already have a VPS?

1. Yes
2. No, help me choose one (recommended)
3. I am not sure
4. Something else

Recommendation: Choose 2 if you want help matching a server to your budget and region.

Reply with a number or your own answer.
~~~

For multi-select questions, say how to answer:

~~~text
Reply with one or more numbers, separated by commas.
~~~

## Recorded answer

Confirm an answer in one line before asking the next question:

~~~text
Recorded: Ubuntu VPS from an existing provider.
~~~

Do not restate the full interview history after every answer.

## Manual action

Use this shape:

~~~text
Aidee install [3/12]
Run host preflight

This command checks the operating system, CPU, memory, disk, SSH, and sudo access. It does not change the server.

Run:

<command in a code block>

Expected result: `Preflight summary: 0 failure(s)`

Reply `done` or paste the error output. Do not paste credentials.
~~~

If the action opens a private authorization page, tell the user to open it themselves. Never ask them to paste the URL, code, key, or token into chat.

## Error

Name the failed check and give one next action:

~~~text
Aidee install paused

Git is not installed on the server.

Run:

<command in a code block>

Reply `done` or paste the error output.
~~~

Do not continue while a required check is failing.

## Plan review

Use these sections:

~~~text
Aidee setup review

Server
<confirmed choices>

Access
<confirmed choices>

Fleet
<confirmed choices>

Credentials
<where credentials will be entered, without values>

Costs
<known recurring and one-time costs>

Actions requiring approval
<destructive, paid, firewall, DNS, and account changes>

Reply `approve` to begin, or name what you want to change.
~~~

## Completion

Report only verified results:

~~~text
Aidee setup complete

Working
<verified services>

Private access
<dashboard access method>

Recovery
<backup status and recovery command>

Still needed
<unfinished manual work, or `Nothing`>
~~~
