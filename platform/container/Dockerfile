ARG HERMES_IMAGE=nousresearch/hermes-agent@sha256:9469b3e78b9545b6d576eb8887a95352e9a0ea83730eaf31431cf862ca1010e1
FROM ${HERMES_IMAGE}

ARG OPENCODE_VERSION=1.18.3

USER root

COPY platform/HERMES_COMMIT \
     platform/HERMES_PATCH_SHA256 \
     platform/HERMES_BASE_FILES_SHA256 \
     platform/HERMES_PATCHED_FILES_SHA256 \
     platform/hermes-runtime-context.patch \
     /opt/aidee/hermes-patch/
COPY --chmod=0755 platform/scripts/apply-hermes-runtime-patch.sh \
     /opt/aidee/hermes-patch/scripts/apply-hermes-runtime-patch.sh
RUN /opt/aidee/hermes-patch/scripts/apply-hermes-runtime-patch.sh /opt/hermes

RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        gh \
        jq \
        socat \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global \
      --allow-scripts=opencode-ai \
      "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force

COPY platform/shared-skills/unslop/ /opt/hermes/skills/unslop/
COPY platform/hermes-plugins/aidee-onboarding/ /opt/hermes/plugins/aidee-onboarding/
COPY platform/dashboard-plugins/aidee-assistant-home/ /opt/hermes/plugins/aidee-assistant-home/
COPY platform/shared-instructions/ /opt/aidee/shared-instructions/
COPY platform/shared-workflows/ /opt/aidee/shared-workflows/
COPY platform/defaults/assistant.yaml /opt/aidee/defaults/assistant.yaml
COPY --chmod=0755 \
     platform/setup/onboarding-gate.py \
     platform/setup/mark-onboarding-step.py \
     /opt/aidee/onboarding/
COPY --chmod=0644 platform/setup/onboarding_state.py /opt/aidee/onboarding/

ARG AIDEE_VERSION
ARG AIDEE_SOURCE_COMMIT
ARG HERMES_VERSION
ARG HERMES_COMMIT
ARG HERMES_PATCH_SHA256

LABEL org.opencontainers.image.title="Aidee Assistant"
LABEL org.opencontainers.image.source="https://github.com/wetek/aidee"
LABEL org.opencontainers.image.version="${AIDEE_VERSION}"
LABEL org.opencontainers.image.revision="${AIDEE_SOURCE_COMMIT}"
LABEL io.aidee.hermes.version="${HERMES_VERSION}"
LABEL io.aidee.hermes.commit="${HERMES_COMMIT}"
LABEL io.aidee.hermes.patch-sha256="${HERMES_PATCH_SHA256}"
LABEL io.aidee.opencode.version="${OPENCODE_VERSION}"

ENV AIDEE_SHARED_ROOT=/opt/aidee

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD hermes --version >/dev/null || exit 1
