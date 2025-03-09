# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY chat-ui/ .
RUN npm install
RUN npm run build

# Stage 2: Build Backend
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend-builder
ADD . /flare-ai-defai
WORKDIR /flare-ai-defai
RUN uv sync --frozen

# Stage 3: Final Image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install nginx
RUN apt-get update && apt-get install -y nginx supervisor curl && \
    rm -rf /var/lib/apt/lists/*

# Install Qdrant
RUN apt-get update && apt-get install -y wget && \
    wget https://github.com/qdrant/qdrant/releases/download/v1.7.3/qdrant-v1.7.3-linux-x86_64.tar.gz && \
    tar -xvf qdrant-v1.7.3-linux-x86_64.tar.gz && \
    mv qdrant /usr/local/bin/ && \
    rm qdrant-v1.7.3-linux-x86_64.tar.gz

WORKDIR /app
COPY --from=backend-builder /flare-ai-defai/.venv ./.venv
COPY --from=backend-builder /flare-ai-defai/src ./src
COPY --from=backend-builder /flare-ai-defai/pyproject.toml .
COPY --from=backend-builder /flare-ai-defai/README.md .

# Copy frontend files
COPY --from=frontend-builder /frontend/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/sites-enabled/default

# Setup supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Allow workload operator to override environment variables
LABEL "tee.launch_policy.allow_env_override"="GEMINI_API_KEY,GEMINI_MODEL,WEB3_PROVIDER_URL,WEB3_EXPLORER_URL,SIMULATE_ATTESTATION"
LABEL "tee.launch_policy.log_redirect"="always"

EXPOSE 80

# Start supervisor (which will start both nginx and the backend)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# Add this line after copying the source code
RUN pip install qdrant-client numpy

# Add this line to copy the qdrant config
COPY qdrant_config.yaml /app/qdrant_config.yaml