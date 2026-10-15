# syntax=docker/dockerfile:1
# The MoneyKata Connector's image (requirements S18.10). Build from this directory:
#   docker buildx build -f connector/Dockerfile -t moneykata-connector:$(cat web/VERSION) connector
# One image for amd64 and arm64: add --platform linux/amd64,linux/arm64.

ARG PYTHON=python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

FROM ${PYTHON} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/connector
COPY requirements.txt ./
# Only the pinned, hashed wheels (S18.1.2); the package itself is copied as it is, with no
# build step, so nothing unpinned is fetched.
RUN python -m venv venv && venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt
COPY moneykata_connector moneykata_connector
RUN printf '#!/bin/sh\nexec /opt/connector/venv/bin/python -m moneykata_connector.main "$@"\n' \
      > venv/bin/moneykata-connector && chmod 0755 venv/bin/moneykata-connector

FROM ${PYTHON}
RUN groupadd --gid 10002 connector \
    && useradd --uid 10002 --gid 10002 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin connector \
    && install -d -o 10002 -g 10002 -m 0700 /var/lib/moneykata-connector /run/moneykata-connector
COPY --from=build /opt/connector /opt/connector
ENV PATH=/opt/connector/venv/bin:$PATH \
    PYTHONPATH=/opt/connector \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10002:10002
VOLUME ["/var/lib/moneykata-connector"]
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD ["moneykata-connector", "status"]
ENTRYPOINT ["moneykata-connector"]
CMD ["serve"]
