FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 \
  python3-venv \
  ffmpeg \
  ca-certificates \
  libnss3 \
  libdbus-1-3 \
  libatk1.0-0 \
  libgbm-dev \
  libasound2 \
  libxrandr2 \
  libxkbcommon-dev \
  libxfixes3 \
  libxcomposite1 \
  libxdamage1 \
  libatk-bridge2.0-0 \
  libpango-1.0-0 \
  libcairo2 \
  libcups2 \
  && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DEMO_VIDEO_BASE=/data/quadro_demo_base.mp4 \
    DEMO_VIDEO_DATA=/data/jobs \
    DEMO_VIDEO_REMOTION=/app/remotion

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/remotion
COPY remotion/package.json remotion/package-lock.json ./
RUN npm ci && npx remotion browser ensure

COPY remotion/src ./src
COPY remotion/public ./public

WORKDIR /app
COPY app ./app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
