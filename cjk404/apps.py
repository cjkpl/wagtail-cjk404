from django.apps import AppConfig


class Managed404Config(AppConfig):
    """Forked from wagtail_managed404, which was abandoned in 2018"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cjk404"

    def ready(self) -> None:
        # Import signal handlers to keep cache in sync with model changes.
        from cjk404 import signals  # noqa: F401  # pylint: disable=unused-import

        return None
