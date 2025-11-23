from __future__ import annotations

from typing import Optional

from django.core.cache import cache

DJANGO_REGEX_REDIRECTS_CACHE_KEY = "django-regex-redirects-regular"
DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY = "django-regex-redirects-regex"
DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT = 60 * 60 * 24 * 7  # 7 Days


def build_cache_key(base_key: str, site_id: Optional[int]) -> str:
    suffix = f":{site_id}" if site_id is not None else ":none"
    return f"{base_key}{suffix}"


def clear_redirect_caches(site_id: Optional[int]) -> None:
    cache.delete(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id))
    cache.delete(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id))
