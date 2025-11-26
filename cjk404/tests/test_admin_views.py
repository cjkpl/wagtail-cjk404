from __future__ import annotations

from typing import List
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.test import override_settings
from django.urls import reverse
from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import build_cache_key
from cjk404.models import PageNotFoundEntry
from cjk404.tests.base import BaseCjk404TestCase


class ClearRedirectCacheViewTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )
        self.client = Client()
        self.client.force_login(self.user)

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

    def test_clear_all_sites_via_get(self) -> None:
        site_ids: List[Optional[int]] = list(Site.objects.values_list("id", flat=True))
        site_ids.append(None)
        self._populate_cache(site_ids)

        response = self.client.get(reverse("cjk404-clear-redirect-cache"))

        self.assertEqual(response.status_code, 302)
        self._assert_cache_cleared(site_ids)

    def test_clear_single_site_via_get(self) -> None:
        default_site_id = Site.objects.first().id  # type: ignore[union-attr]
        secondary_site = self.create_site("secondary.example.com")
        target_ids: List[Optional[int]] = [default_site_id, secondary_site.id, None]
        self._populate_cache(target_ids)

        response = self.client.get(
            reverse("cjk404-clear-redirect-cache"), {"site_id": secondary_site.id}
        )

        self.assertEqual(response.status_code, 302)
        self._assert_cache_cleared([secondary_site.id])
        self._assert_cache_present([default_site_id, None])


class ImportBuiltinRedirectsViewTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_imports_all_sites_via_get(self) -> None:
        self.create_site("secondary.example.com")
        response = self.client.get(reverse("cjk404-import-builtin-redirects"))

        self.assertEqual(response.status_code, 302)
        site_count = Site.objects.count()
        self.assertEqual(
            PageNotFoundEntry.objects.count(),
            len(BUILTIN_REDIRECTS) * site_count,
        )
        self.assertTrue(all(not entry.is_active for entry in PageNotFoundEntry.objects.all()))

    def test_imports_single_site_and_skips_existing(self) -> None:
        secondary_site = self.create_site("secondary.example.com")
        built_in = BUILTIN_REDIRECTS[0]
        PageNotFoundEntry.objects.create(
            site=secondary_site,
            url=built_in.url,
            regular_expression=built_in.regular_expression,
            is_active=True,
        )

        response = self.client.get(
            reverse("cjk404-import-builtin-redirects"), {"site_id": secondary_site.id}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            PageNotFoundEntry.objects.filter(site=secondary_site).count(),
            len(BUILTIN_REDIRECTS),
        )
        self.assertEqual(
            PageNotFoundEntry.objects.exclude(site=secondary_site).count(),
            0,
        )

    def test_import_invalid_site_is_safe(self) -> None:
        response = self.client.get(reverse("cjk404-import-builtin-redirects"), {"site_id": 99999})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PageNotFoundEntry.objects.count(), 0)

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_header_button_shows_existing_counts(self) -> None:
        list_url = reverse("wagtailsnippets_cjk404_pagenotfoundentry:list")
        response = self.client.get(list_url)
        self.assertContains(response, f"Import Built-in Redirects (0/{len(BUILTIN_REDIRECTS)})")

        built_in = BUILTIN_REDIRECTS[0]
        PageNotFoundEntry.objects.create(
            site=Site.objects.first(),
            url=built_in.url,
            regular_expression=built_in.regular_expression,
        )

        response = self.client.get(list_url)
        self.assertContains(response, f"Import Built-in Redirects (1/{len(BUILTIN_REDIRECTS)})")
