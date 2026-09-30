FROM python:3.12-slim

ARG COMMUNITY_VERSION=0.1.0
ARG COMMUNITY_WHEEL_SHA256=unknown

LABEL org.opencontainers.image.title="RadiusDeck" \
      org.opencontainers.image.description="Community web UI for FreeRADIUS client management" \
      org.opencontainers.image.version="${COMMUNITY_VERSION}" \
      org.radiusdeck.community-wheel-sha256="${COMMUNITY_WHEEL_SHA256}"

COPY dist/community/radiusdeck-*.whl /tmp/community-wheels/
RUN python -m pip install --no-cache-dir /tmp/community-wheels/radiusdeck-*.whl \
    && rm -rf /tmp/community-wheels

COPY dist/community/community-installed-manifest.json \
     /usr/local/share/radiusdeck/community-installed-manifest.json

RUN groupadd --gid 10001 radiusdeck \
    && useradd --uid 10001 --gid 10001 --no-create-home \
       --home-dir /app --shell /usr/sbin/nologin radiusdeck \
    && mkdir -p /app /data /backups \
    && chown -R radiusdeck:radiusdeck /app /data /backups

WORKDIR /app
USER 10001:10001

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_RADIUS_CLIENTS_PATH=/data/clients.conf \
    APP_BACKUP_DIR=/backups

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["radiusdeck", "serve"]
