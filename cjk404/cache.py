from __future__ import annotations

from typing import Optional

from django.core.cache import cache

DJANGO_REGEX_REDIRECTS_CACHE_KEY = "django-regex-redirects-regular-v2"
DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY = "django-regex-redirects-regex-v2"
DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT = 60 * 60 * 24 * 7  # 7 Days

LEGACY_DJANGO_REGEX_REDIRECTS_CACHE_KEY = "django-regex-redirects-regular"
LEGACY_DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY = "django-regex-redirects-regex"


def build_cache_key(base_key: str, site_id: Optional[int]) -> str:
    suffix = f":{site_id}" if site_id is not None else ":none"
    return f"{base_key}{suffix}"


def clear_redirect_caches(site_id: Optional[int]) -> None:
    base_keys = (
        DJANGO_REGEX_REDIRECTS_CACHE_KEY,
        DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY,
        LEGACY_DJANGO_REGEX_REDIRECTS_CACHE_KEY,
        LEGACY_DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY,
    )
    cache.delete_many([build_cache_key(base_key, site_id) for base_key in base_keys])
