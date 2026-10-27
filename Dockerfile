FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HF_HOME=/models \
    HUGGINGFACE_HUB_CACHE=/models \
    XDG_CACHE_HOME=/models \
    DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /data /models /ms-playwright

COPY pyproject.toml README.md ./
COPY capservice ./capservice

RUN pip install --no-cache-dir . \
    && python -m playwright install chromium --with-deps \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('base')" \
    && rm -rf /root/.cache/pip

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /data /models /ms-playwright

USER appuser
VOLUME ["/data"]
EXPOSE 8000

ENTRYPOINT ["python", "-m", "capservice"]
CMD ["api"]
