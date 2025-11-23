from __future__ import annotations

from typing import List
from typing import Optional

from django.core.cache import cache
from django.core.management import CommandError
from django.core.management import call_command
from wagtail.models import Site

from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import build_cache_key
from cjk404.tests.base import BaseCjk404TestCase


class ClearRedirectCacheCommandTests(BaseCjk404TestCase):
    def _populate_cache(self, site_ids: List[Optional[int]]) -> None:
        for site_id in site_ids:
            cache.set(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id), ["sentinel"], 300)
            cache.set(
                build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id),
                ["sentinel"],
                300,
            )

    def _assert_cache_cleared(self, site_ids: List[Optional[int]]) -> None:
        for site_id in site_ids:
            self.assertIsNone(cache.get(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id)))
            self.assertIsNone(
                cache.get(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id))
            )

    def _assert_cache_present(self, site_ids: List[Optional[int]]) -> None:
        for site_id in site_ids:
            self.assertIsNotNone(
                cache.get(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id))
            )
            self.assertIsNotNone(
                cache.get(build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id))
            )

    def test_command_clears_all_redirect_caches(self) -> None:
        site_ids: List[Optional[int]] = list(Site.objects.values_list("id", flat=True))
        site_ids.append(None)
        self._populate_cache(site_ids)

        call_command("clear_redirect_cache")

        self._assert_cache_cleared(site_ids)

    def test_command_rejects_unknown_site(self) -> None:
        existing_ids = list(Site.objects.values_list("id", flat=True))
        invalid_site_id = max(existing_ids) + 1000 if existing_ids else 9999

        with self.assertRaises(CommandError):
            call_command("clear_redirect_cache", site_id=invalid_site_id)

    def test_command_can_target_single_site(self) -> None:
        default_site_id = Site.objects.first().id  # type: ignore[union-attr]
        secondary_site = self.create_site("secondary.example.com")
        site_ids: List[Optional[int]] = [default_site_id, secondary_site.id, None]
        self._populate_cache(site_ids)

        call_command("clear_redirect_cache", site_id=secondary_site.id)

        self._assert_cache_present([default_site_id, None])
        self._assert_cache_cleared([secondary_site.id])
