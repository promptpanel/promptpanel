FROM python:3.10-slim

# Working dir
WORKDIR /app

# Copy app files
COPY . /app

# Add opencontainers labels
LABEL org.opencontainers.image.source=https://github.com/promptpanel/promptpanel
LABEL org.opencontainers.image.description="Prompt Panel - Accelerating your AI agent adoption"

# Add ARGs
ARG PROMPT_VERSION=
# Set environment variables
ENV DEBIAN_FRONTEND=nointeractive \
    PIP_ROOT_USER_ACTION=ignore \
    PROMPT_VERSION=$PROMPT_VERSION \
    PROMPT_HEAD=ENABLED \
    PROMPT_BRAND_COLOR=#2D72D2 \
    PROMPT_LOG_LEVEL=ERROR \
    PROMPT_MODE=DEVELOPMENT \
    PROMPT_DEV_REQS=DISABLED \
    PROMPT_OPS_BASE=https://ops.promptpanel.com \
    PROMPT_WORKERS=2 \
    PROMPT_WORKER_TIMEOUT=600

# Update pip and install requirements
RUN apt update -y && apt upgrade -y && apt install curl cron gcc libpq-dev libgl1-mesa-glx libglib2.0-0 poppler-utils sqlite3 tesseract-ocr -y
RUN pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --upgrade pip && find . -name requirements.txt -exec pip install --no-cache-dir -r {} \; && \
    find /tmp -mindepth 1 -delete

# Entrypoint
CMD ["/bin/sh", "-c", "chmod +x /app/entrypoint.sh && /app/entrypoint.sh"]