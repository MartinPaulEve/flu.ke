# Local CMS / static-site generator for flu.ke.
# This image runs the PRIVATE editing environment (Django admin + management
# commands). The public site is the static output of `build_site` — it is not
# served by this image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.11.11

WORKDIR /app

# Dependencies only (cached unless the lockfile changes). The venv lives at
# /opt/venv — outside /app — so the runtime bind-mount of the repo never hides it.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
