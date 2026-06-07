"""Admin action to move a resource file (its file + metadata) to another resource."""

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import reverse

from apps.resources.models import Resource, ResourceFile

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:resources_resourcefile_changelist"


def _setup():
    r1 = Resource.objects.create(title="Resource1", kind="fan")
    r2 = Resource.objects.create(title="Resource2", kind="fan")
    rf = ResourceFile.objects.create(
        resource=r1, original_filename="file1.mp3", file="resources/file1.mp3", file_kind="audio"
    )
    return rf, r2


def test_move_action_renders_resource_picker(admin_client):
    rf, _ = _setup()
    resp = admin_client.post(
        reverse(CHANGELIST),
        {"action": "move_to_resource", ACTION_CHECKBOX_NAME: [str(rf.pk)]},
    )
    assert resp.status_code == 200
    assert b"Target resource" in resp.content


def test_move_action_reassigns_file_keeping_metadata(admin_client):
    rf, r2 = _setup()
    admin_client.post(
        reverse(CHANGELIST),
        {
            "action": "move_to_resource",
            ACTION_CHECKBOX_NAME: [str(rf.pk)],
            "apply": "1",
            "resource": str(r2.pk),
        },
    )
    rf.refresh_from_db()
    assert rf.resource_id == r2.pk                 # moved to Resource2
    assert rf.original_filename == "file1.mp3"     # metadata travels with it
