FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium ffmpeg libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 libcups2 fonts-liberation ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/code-motion
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
RUN chmod -R a+rX /opt/code-motion
ENV HOME=/tmp
ENV REMOTION_BROWSER_EXECUTABLE=/usr/bin/chromium
ENTRYPOINT ["node", "/opt/code-motion/src/worker.mjs", "/job"]
