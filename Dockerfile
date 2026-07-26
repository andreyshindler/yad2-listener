FROM python:3.11-slim

# Don't buffer stdout/stderr so logs show up immediately in `docker logs`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY main.py .
COPY yad2_listener ./yad2_listener

# Persist the seen-ids state outside the image layer.
ENV STATE_FILE=/data/state.json
VOLUME ["/data"]

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

ENTRYPOINT ["python", "main.py"]
