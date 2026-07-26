# Playwright's image ships Chromium + all the system libraries it needs, so the
# headless browser that gets past Yad2's bot challenge works out of the box.
FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

# Don't buffer stdout/stderr so logs show up immediately in `docker logs`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching. Chromium already ships
# in the base image (matching the pinned playwright version), so no browser
# download is needed here.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY main.py .
COPY yad2_listener ./yad2_listener

# Persist the seen-ids state outside the image layer.
ENV STATE_FILE=/data/state.json
VOLUME ["/data"]

# Run Chromium headful under a virtual display (Xvfb) — a real on-screen
# browser is far harder for Radware Bot Manager to fingerprint than headless.
ENV YAD2_HEADLESS=0

# The Playwright image already has a non-root `pwuser`; run as them.
RUN mkdir -p /data && chown -R pwuser:pwuser /data /app
USER pwuser

# xvfb-run provides the virtual display; CLI args pass straight through.
ENTRYPOINT ["xvfb-run", "-a", "python", "main.py"]
