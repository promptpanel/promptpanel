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
    # PromptPanel specific
    PROMPT_ACCESS_TOKEN_EXP_MINUTES=480 \
    PROMPT_REFRESH_TOKEN_EXP_MINUTES=43200 \
    PROMPT_BRAND_COLOR=#2D72D2 \
    PROMPT_HEAD=ENABLED \
    PROMPT_LOG_LEVEL=ERROR \
    PROMPT_LICENSE_EMAIL= \
    PROMPT_LICENSE_KEY= \
    PROMPT_MAX_FILESIZE=26214400 \
    PROMPT_MODE=DEVELOPMENT \
    PROMPT_OPS_BASE=https://ops.promptpanel.com \
    PROMPT_SMTP_USE_TLS="True" \
    PROMPT_SMTP_PORT=587 \
    PROMPT_SMTP_USER= \
    PROMPT_SMTP_PASSWORD= \
    PROMPT_SMTP_FROM_ADDRESS= \
    PROMPT_USER_ALLOWED_DOMAINS= \
    PROMPT_VERSION=$PROMPT_VERSION \
    PROMPT_WORKERS=2 \
    PROMPT_WORKER_TIMEOUT=600 \
    # Disabled-by-default envs
    PROMPT_DEV_INSTALL_REQS=DISABLED \
    PROMPT_SECRET_KEY=DISABLED \
    PROMPT_OLLAMA_HOST=DISABLED \
    PROMPT_OIDC_DISPLAY_NAME=DISABLED \
    PROMPT_OIDC_CLIENT_ID=DISABLED \
    PROMPT_OIDC_CLIENT_SECRET=DISABLED \
    PROMPT_OIDC_AUTHORIZE_URL=DISABLED \
    PROMPT_OIDC_ACCESS_TOKEN_URL=DISABLED \
    PROMPT_OIDC_USERINFO_URL=DISABLED \
    PROMPT_OIDC_KWARGS=DISABLED \
    PROMPT_PG_HOST=DISABLED \
    PROMPT_PG_PORT=DISABLED \
    PROMPT_PG_DBNAME=DISABLED \
    PROMPT_PG_USER=DISABLED \
    PROMPT_PG_PASS=DISABLED \
    PROMPT_SQLITE_WAL=DISABLED \
    PROMPT_SMTP_HOST=DISABLED \
    PROMPT_USER_SIGNUP=DISABLED \
    PROMPT_USER_SIGNUP_ACTIVATE=DISABLED \
    PROMPT_USER_RESET_PASSWORD=DISABLED

# Update pip and install requirements
RUN apt update -y && apt upgrade -y && apt install curl cron gcc libpq-dev libgl1-mesa-glx libglib2.0-0 poppler-utils sqlite3 tesseract-ocr -y
RUN pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --upgrade pip && find . -name requirements.txt -exec pip install --no-cache-dir -r {} \; && \
    find /tmp -mindepth 1 -delete

# Entrypoint
CMD ["/bin/sh", "-c", "chmod +x /app/entrypoint.sh && /app/entrypoint.sh"]