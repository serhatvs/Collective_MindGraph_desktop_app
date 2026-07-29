# Rootless image for the content-free synchronization service.
FROM python:3.13-slim AS build

WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels ".[sync-server]"

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CMG_SYNC_BLOB_ROOT=/var/lib/mindgraph/blobs

RUN useradd --create-home --uid 10001 mindgraph \
    && mkdir -p /var/lib/mindgraph/blobs \
    && chown -R mindgraph:mindgraph /var/lib/mindgraph

COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels collective-mindgraph[sync-server] \
    && rm -rf /wheels

USER 10001
EXPOSE 8443

# The service binds every interface inside the container; the deployment's
# ingress terminates TLS and is the only path that should reach this port.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8443/sync/v1/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["mindgraph-sync-server", "--host", "0.0.0.0", "--port", "8443"]
