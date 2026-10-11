FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 POCKETGRID_DATA=/data POCKETGRID_WEB_DIR=/app/apps/web/dist
WORKDIR /app
COPY services/coordinator/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd --uid 10001 --create-home pocketgrid && mkdir /data && chown pocketgrid /data
COPY services/ ./services/
COPY --from=web /web/dist ./apps/web/dist/
USER pocketgrid
EXPOSE 8787
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8787/api/health')"
# Only Caddy can reach this port, and it overwrites X-Forwarded-For, so per-client
# sign-in rate limits see real addresses.
CMD ["uvicorn", "services.coordinator.app:app", "--host", "0.0.0.0", "--port", "8787", "--no-access-log", "--forwarded-allow-ips", "*"]
