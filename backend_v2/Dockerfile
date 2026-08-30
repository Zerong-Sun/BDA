FROM python:3.13-slim

ARG BDA_BUILD_REVISION=development
ARG BDA_SCHEMA_REVISION=0051_worker_project_rls

WORKDIR /app
# Pick up patched Debian packages (util-linux, libblkid, libmount, libuuid, etc.)
# ahead of the next python:3.13-slim image refresh, to keep the Trivy CVE gate green.
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends openssh-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY backend_v2 backend_v2
COPY frontend/public/research-packages frontend/public/research-packages
# pip and setuptools are build tooling, and nothing at runtime uses them - the image runs
# uvicorn and alembic, neither of which installs anything. Leaving them in ships the base
# image's setuptools and pip's vendored msgpack as part of the attack surface, which is
# where both of the container scan's HIGH findings live. Removed after the install rather
# than upgraded: an upgrade only moves the problem to the next advisory.
RUN pip install --no-cache-dir --require-hashes -r backend_v2/requirements.lock \
    && pip install --no-cache-dir --no-deps ./backend_v2
# Separate layer, and deliberately no `|| true`: swallowing the exit code here would turn a
# failed install into an image that builds clean and contains nothing.
RUN pip uninstall --yes setuptools wheel pip
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/lib/bda/secrets \
    && chown -R appuser:appuser /app /var/lib/bda/secrets \
    && chmod 700 /var/lib/bda/secrets
USER appuser
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 \
    BDA_V2_BUILD_REVISION=${BDA_BUILD_REVISION} \
    BDA_V2_SCHEMA_REVISION=${BDA_SCHEMA_REVISION}
EXPOSE 8200
CMD ["uvicorn", "backend_v2.app.main:app", "--host", "0.0.0.0", "--port", "8200"]
