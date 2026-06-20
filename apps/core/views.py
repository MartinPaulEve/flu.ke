"""Small admin-only views (e.g. the rich-text editor's image upload endpoint)."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.models import Upload


@csrf_exempt
@staff_member_required
@require_POST
def tinymce_upload(request):
    """Receive an image from the TinyMCE editor, store it as an Upload, and return
    its URL in the ``{"location": ...}`` shape TinyMCE expects.

    Restricted to logged-in staff (the only people with editor access). CSRF is
    exempt because TinyMCE's uploader posts the file without a CSRF token and the
    endpoint only ever creates a stored file behind admin authentication.
    """
    upload_file = request.FILES.get("file")
    if upload_file is None:
        return HttpResponseBadRequest("No file was uploaded.")
    upload = Upload.objects.create(title=upload_file.name, file=upload_file)
    return JsonResponse({"location": upload.file.url})
