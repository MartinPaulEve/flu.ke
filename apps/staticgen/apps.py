from django.apps import AppConfig


class StaticgenConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.staticgen"
    label = "staticgen"

    def ready(self):
        from apps.staticgen import signals

        signals.connect()
