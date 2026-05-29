#!/usr/bin/env bash
#
# Deploy the generated static site (dist/) to a large-file-capable static host.
# The CMS is private; this ships only the rendered output, so the public site
# runs no application code.
#
# Configure via environment or .env:
#   DEPLOY_TARGET        rsync | s3 | rclone     (required)
#   DEPLOY_BUILD         1 to run build_site first (default 1)
#   # rsync (to an nginx box):
#   DEPLOY_RSYNC_DEST    e.g. deploy@flu.ke:/var/www/flu.ke
#   # s3 (S3 / R2 / B2 with an S3 API):
#   DEPLOY_S3_BUCKET     e.g. s3://flu.ke
#   AWS_* / endpoint     standard aws-cli env (set AWS_ENDPOINT_URL for R2/B2)
#   # rclone:
#   DEPLOY_RCLONE_REMOTE e.g. r2:flu-ke
#
# Usage:  bash scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load .env if present (for DEPLOY_* and Django settings).
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DIST="${BUILD_DIR:-dist}"
DEPLOY_TARGET="${DEPLOY_TARGET:?Set DEPLOY_TARGET to rsync, s3 or rclone}"
DEPLOY_BUILD="${DEPLOY_BUILD:-1}"

if [[ "$DEPLOY_BUILD" == "1" ]]; then
  echo "==> Building static site into $DIST"
  uv run python manage.py build_site
fi

if [[ ! -f "$DIST/index.html" ]]; then
  echo "ERROR: $DIST/index.html not found — build first." >&2
  exit 1
fi

case "$DEPLOY_TARGET" in
  rsync)
    : "${DEPLOY_RSYNC_DEST:?Set DEPLOY_RSYNC_DEST (user@host:/path)}"
    echo "==> rsync -> $DEPLOY_RSYNC_DEST"
    # --checksum so unchanged large media is skipped; --delete removes stale files.
    rsync -avh --checksum --delete "$DIST"/ "$DEPLOY_RSYNC_DEST"/
    echo "Note: set cache + MIME headers in nginx (see scripts/nginx-flu.ke.conf)."
    ;;

  s3)
    : "${DEPLOY_S3_BUCKET:?Set DEPLOY_S3_BUCKET (s3://bucket)}"
    EP=()
    [[ -n "${AWS_ENDPOINT_URL:-}" ]] && EP=(--endpoint-url "$AWS_ENDPOINT_URL")
    echo "==> aws s3 sync -> $DEPLOY_S3_BUCKET"
    # Pass 1: everything except HTML — long cache (immutable-ish static + media).
    aws "${EP[@]}" s3 sync "$DIST" "$DEPLOY_S3_BUCKET" \
      --size-only --exclude "*.html" --exclude "*.xml" --exclude "*.txt" \
      --cache-control "public, max-age=31536000, immutable"
    # Pass 2: HTML/feed/sitemap/robots — short cache so edits go live promptly.
    aws "${EP[@]}" s3 sync "$DIST" "$DEPLOY_S3_BUCKET" \
      --size-only --exclude "*" --include "*.html" --include "*.xml" --include "*.txt" \
      --cache-control "public, max-age=300, must-revalidate"
    # Ensure correct content types for archive formats the SDK may mislabel.
    aws "${EP[@]}" s3 cp "$DIST" "$DEPLOY_S3_BUCKET" --recursive \
      --exclude "*" --include "*.rar" --content-type "application/vnd.rar" \
      --metadata-directive REPLACE --cache-control "public, max-age=31536000, immutable" || true
    ;;

  rclone)
    : "${DEPLOY_RCLONE_REMOTE:?Set DEPLOY_RCLONE_REMOTE (remote:bucket)}"
    echo "==> rclone sync -> $DEPLOY_RCLONE_REMOTE"
    rclone sync "$DIST" "$DEPLOY_RCLONE_REMOTE" --checksum --fast-list \
      --header-upload "Cache-Control: public, max-age=31536000, immutable"
    ;;

  *)
    echo "ERROR: unknown DEPLOY_TARGET '$DEPLOY_TARGET' (use rsync|s3|rclone)" >&2
    exit 2
    ;;
esac

echo "==> Done."
