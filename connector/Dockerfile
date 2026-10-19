# syntax=docker/dockerfile:1
# The MoneyKata Connector's image (requirements S18.10), published as
# ghcr.io/mojokata/moneykata-connector (S17.8.2). To build it yourself, from the repository's root:
#   docker buildx build -f connector/Dockerfile -t ghcr.io/mojokata/moneykata-connector:$(cat web/VERSION) --load connector
# Another architecture: add --platform linux/arm64 (or amd64), which runs under QEMU.

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
LABEL org.opencontainers.image.source="https://github.com/MojoKata/MoneyKata" \
      org.opencontainers.image.description="The MoneyKata Connector: keeps accounts current from their institutions"
USER 10002:10002
VOLUME ["/var/lib/moneykata-connector"]
# Its page (S18.11), its one listening port.
EXPOSE 37374
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD ["moneykata-connector", "status"]
ENTRYPOINT ["moneykata-connector"]
CMD ["serve"]
