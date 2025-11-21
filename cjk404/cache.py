from __future__ import annotations

from typing import Optional

from django.core.cache import cache

DJANGO_REGEX_REDIRECTS_CACHE_KEY = "django-regex-redirects-regular"
DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY = "django-regex-redirects-regex"
DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT = 60


def build_cache_key(base_key: str, site_id: Optional[int]) -> str:
    """Return the cache key used for storing redirects per site.

    The middleware keeps a separate cache entry per site to avoid cross-site
    leakage. Using a dedicated helper keeps this logic in one place so that
    invalidation can reuse it reliably.
    """

    suffix = f":{site_id}" if site_id is not None else ":none"
    return f"{base_key}{suffix}"


def clear_redirect_caches(site_id: Optional[int]) -> None:
    """Remove cached redirect lookups for the given site.

    The cache lifetime is short, but tests and admin updates expect changes to
    apply immediately. Clearing both the regular and regex caches ensures
    deterministic behaviour.
    """

    cache.delete(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id))
    cache.delete(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id))
