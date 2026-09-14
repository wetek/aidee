# Assistant directories

Provisioning creates one directory per assistant.

~~~text
<assistant-id>/
  SOUL.md
  assistant.yaml
  memories/
    MEMORY.md
    USER.md
  skills/
  cron/
  knowledge/
  project.yaml or projects.yaml
~~~

The controller mounts approved paths into only that assistant's container. It never mounts the entire fleet directory.

Each assistant also receives a private runtime directory at
`/opt/data/aidee/repos`. Coding agents store all cloned repositories there.
Fleet updates relocate leftover git checkouts from the assistant Hermes home
into that directory. A real checkout that already uses the name stays, and the
leftover clone is moved to `/opt/data/aidee/legacy-home-repos`. A file or
symlink occupying the name is moved there instead so the leftover clone can
take the canonical path.
