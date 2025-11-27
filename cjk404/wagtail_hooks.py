from cjk404.hooks import admin_urls  # noqa: F401 - ensures hook registration
from cjk404.hooks.filters import PageNotFoundEntryFilterSet, multiple_sites_exist
from cjk404.hooks.views import PageNotFoundEntryViewSet
from wagtail.snippets.models import register_snippet

register_snippet(PageNotFoundEntryViewSet)

__all__ = [
    "PageNotFoundEntryFilterSet",
    "PageNotFoundEntryViewSet",
    "multiple_sites_exist",
]
