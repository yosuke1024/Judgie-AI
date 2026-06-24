# --- Stage 1: Build the React frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

# Copy frontend packages and install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy the frontend source and build it
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Create the runtime image ---
FROM python:3.11-slim
WORKDIR /app

# Install minimal system tools required for litestream and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and install Litestream
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        LITESTREAM_ARCH="arm64"; \
    else \
        LITESTREAM_ARCH="amd64"; \
    fi && \
    curl -sL "https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-${LITESTREAM_ARCH}.deb" -o /tmp/litestream.deb && \
    dpkg -i /tmp/litestream.deb && \
    rm /tmp/litestream.deb

# Copy Python requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy litestream configurations
COPY litestream.yml ./

# Copy backend app source code
COPY backend/app/ ./app

# Copy assets required for custom avatars
COPY assets/ ./assets

# Copy global templates required by templates.py
COPY templates/ ./templates

# Copy the built React assets to static directory for FastAPI to serve
COPY --from=frontend-builder /frontend/dist/ ./static

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
