"""Small admin-only views (e.g. the rich-text editor's image upload endpoint)."""

from urllib.parse import urlparse

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from PIL import Image, UnidentifiedImageError

from apps.core.models import Upload

# The uploader accepts raster images only, verified by their actual content (not
# the client-supplied name). SVG and other markup formats are rejected: served
# from our own origin they can execute script on direct navigation (stored XSS).
_FORMAT_EXTENSION = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp"}


def _is_same_origin(request) -> bool:
    """Whether the POST comes from this site.

    A CSRF defence that needs no token: browsers set Origin (and Referer) on
    cross-site POSTs and a malicious page cannot forge them, so requiring them to
    match our host blocks cross-site uploads. TinyMCE's uploader posts without a
    CSRF token, and django-tinymce's JSON config can't supply a custom upload
    handler to add one, so this is the equivalent protection.
    """
    host = request.get_host()
    for header in ("HTTP_ORIGIN", "HTTP_REFERER"):
        value = request.META.get(header)
        if value:
            return urlparse(value).netloc == host
    return False


@csrf_exempt
@staff_member_required
@require_POST
def tinymce_upload(request):
    """Receive an image from the TinyMCE editor, store it as an Upload, and return
    its URL in the ``{"location": ...}`` shape TinyMCE expects.

    Hardened: restricted to logged-in staff and same-origin requests; the bytes
    are verified to be a real raster image with Pillow and the stored extension
    is taken from the verified format, never the client filename.
    """
    if not _is_same_origin(request):
        return HttpResponseForbidden("Cross-origin upload refused.")
    upload_file = request.FILES.get("file")
    if upload_file is None:
        return HttpResponseBadRequest("No file was uploaded.")
    try:
        image = Image.open(upload_file)
        image_format = image.format
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return HttpResponseBadRequest("Not a valid image.")
    extension = _FORMAT_EXTENSION.get(image_format)
    if extension is None:
        return HttpResponseBadRequest("Unsupported image type.")

    original_name = upload_file.name
    upload_file.seek(0)
    upload_file.name = f"image{extension}"  # stored name uses the *verified* type
    upload = Upload.objects.create(title=original_name, file=upload_file)
    return JsonResponse({"location": upload.file.url})
