# syntax=docker/dockerfile:1
# MoneyKata's image (requirements S17.8). Build from the repository's root:
#   docker buildx build -f web/install/Dockerfile -t moneykata:$(cat web/VERSION) .
# One image for amd64 and arm64: add --platform linux/amd64,linux/arm64 (arm64 under QEMU).

ARG PYTHON=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

FROM ${PYTHON} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PROJECT_ENVIRONMENT=/opt/moneykata/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY web/install/build-requirements.txt /tmp/
RUN pip install --no-cache-dir --require-hashes -r /tmp/build-requirements.txt
WORKDIR /opt/moneykata
# Dependencies first, from the lock with its hashes, so a code change reuses this layer.
COPY web/VERSION web/
COPY web/server/pyproject.toml web/server/uv.lock web/server/
RUN cd web/server && uv sync --frozen --no-dev --no-install-project
COPY web/server/src web/server/src
RUN cd web/server && uv sync --frozen --no-dev
COPY web/ui web/ui
RUN python3 web/ui/vendor/vendor.py extract \
    && rm -f web/ui/vendor/*.tgz \
    && rm -rf web/ui/tests web/ui/mockup
COPY docs/mockups/MoneyKata-mock.html docs/mockups/

FROM ${PYTHON}
RUN groupadd --gid 10001 moneykata \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin moneykata \
    && install -d -o 10001 -g 10001 -m 0700 /var/lib/moneykata /var/backups/moneykata \
    && install -d -o 0 -g 0 -m 0755 /etc/moneykata
COPY --from=build /opt/moneykata /opt/moneykata
ENV PATH=/opt/moneykata/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 37373
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["moneykata", "health"]
ENTRYPOINT ["moneykata"]
CMD ["serve"]
