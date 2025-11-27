from django.apps import AppConfig


class Managed404Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cjk404"

    def ready(self) -> None:
        from cjk404 import signals  # noqa: F401  # pylint: disable=unused-import
        return None
