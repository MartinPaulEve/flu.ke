# Local CMS image for fluke.fm.
# This image runs the PRIVATE editing environment (Django admin + management
# commands) for local content editing. The public site is served live by the
# Django app (apps.frontend + apps.api); see docs/deploy-docker.md for the
# production deployment.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.11.11

# ffmpeg: required by the `audio_samples` management command (extracting fading
# track samples). Installed here, early, so the layer is cached.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies only (cached unless the lockfile changes). The venv lives at
# /opt/venv — outside /app — so the runtime bind-mount of the repo never hides it.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Run as a non-root user whose UID/GID match the host (override at build time with
# --build-arg UID=$(id -u) GID=$(id -g)). This way files the container writes into
# the bind-mounted working tree (db.sqlite3, media/) are owned by you, not root.
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "$GID" app || true \
 && useradd --uid "$UID" --gid "$GID" --create-home --shell /bin/bash app \
 && chmod -R a+rX /opt/venv
ENV HOME=/home/app
USER app

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
