from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self):
        # Invalidate the whole-site page cache whenever any content object
        # changes (covers admin edits, imports and OG regeneration).
        from django.db.models.signals import post_delete, post_save

        from apps.core.cache import invalidate_on_content_change

        post_save.connect(invalidate_on_content_change, dispatch_uid="core.cache.save")
        post_delete.connect(invalidate_on_content_change, dispatch_uid="core.cache.delete")
