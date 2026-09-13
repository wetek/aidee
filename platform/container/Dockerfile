ARG HERMES_IMAGE=nousresearch/hermes-agent@sha256:9469b3e78b9545b6d576eb8887a95352e9a0ea83730eaf31431cf862ca1010e1
FROM ${HERMES_IMAGE}

ARG AIDEE_VERSION
ARG AIDEE_SOURCE_COMMIT
ARG OPENCODE_VERSION=1.18.3

USER root

RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        gh \
        jq \
        socat \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force

COPY platform/shared-skills/unslop/ /opt/hermes/skills/unslop/
COPY platform/shared-instructions/ /opt/aidee/shared-instructions/
COPY platform/shared-workflows/ /opt/aidee/shared-workflows/
COPY platform/defaults/assistant.yaml /opt/aidee/defaults/assistant.yaml

LABEL org.opencontainers.image.title="Aidee Assistant"
LABEL org.opencontainers.image.source="https://github.com/wetek/aidee"
LABEL org.opencontainers.image.version="${AIDEE_VERSION}"
LABEL org.opencontainers.image.revision="${AIDEE_SOURCE_COMMIT}"
LABEL io.aidee.hermes.version="v2026.9.11"
LABEL io.aidee.opencode.version="${OPENCODE_VERSION}"

ENV AIDEE_SHARED_ROOT=/opt/aidee

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD hermes --version >/dev/null || exit 1
