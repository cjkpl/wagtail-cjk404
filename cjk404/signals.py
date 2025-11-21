from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from cjk404.cache import clear_redirect_caches
from cjk404.models import PageNotFoundEntry


@receiver([post_save, post_delete], sender=PageNotFoundEntry)
def invalidate_redirect_cache(sender: type[PageNotFoundEntry], instance: PageNotFoundEntry, **_: Any) -> None:
    """Ensure redirect caches refresh when entries change.

    Without invalidation, newly created redirects would not be honoured until
    the cache timeout expires, which breaks test isolation and surprises users
    immediately after updates.
    """

    clear_redirect_caches(instance.site_id)
