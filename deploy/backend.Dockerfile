FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/NavidPMB/tasklane" org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home tasklane \
    && mkdir -p /data/private /data/static \
    && chown -R tasklane:tasklane /data
COPY backend backend
COPY VERSION VERSION
COPY deploy/backend-entrypoint.sh deploy/backend-entrypoint.sh
RUN chmod 755 deploy/backend-entrypoint.sh
WORKDIR /app/backend
USER tasklane
EXPOSE 8010
ENTRYPOINT ["/app/deploy/backend-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8010", "--workers", "2", "--no-proxy-headers"]
