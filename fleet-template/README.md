# Aidee fleet template

Templates for private controller configuration and assistant-specific meaningful state.

Setup copies these files to `/var/lib/aidee/fleet`. Do not store a deployed fleet in the public Aidee repository.

The Aidee controller is the only Git writer for generated fleet state. Each assistant receives bind mounts for its own approved files and directories. Assistants do not receive repository credentials or access to another assistant's directory.

## Layout

~~~text
registry.yaml.template  Template for the deployed assistant inventory
controller/          Aidee controller identity and infrastructure declarations
assistants/          One isolated directory per assistant
~~~

Project details that the controller does not operate, such as work tracker configuration, remain inside that assistant's generated directory and outside the registry.

## Secrets

Do not store secrets here. Enter them through masked terminal input or the protected Hermes dashboard. Secret and runtime state live outside generated fleet state and use encrypted backups where recovery requires them.

## Filesystem synchronization

Tracked assistant paths are host files bind-mounted into the container. A memory update changes the host file immediately. Hermes hooks notify the controller after memory writes and session completion; the controller scans, commits, and pushes the change.
