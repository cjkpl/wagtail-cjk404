from __future__ import annotations

from typing import List
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import CommandError
from django.core.management import call_command
from django.test import override_settings
from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.builtin_redirects import BuiltinRedirect
from cjk404.builtin_redirects import import_builtin_redirects_for_site
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import build_cache_key
from cjk404.models import PageNotFoundEntry
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


class ImportBuiltinRedirectsCommandTests(BaseCjk404TestCase):
    def test_imports_for_all_sites(self) -> None:
        self.create_site("secondary.example.com")
        call_command("import_builtin_redirects")

        site_count = Site.objects.count()
        self.assertEqual(
            PageNotFoundEntry.objects.count(),
            len(BUILTIN_REDIRECTS) * site_count,
        )
        self.assertTrue(all(not entry.is_active for entry in PageNotFoundEntry.objects.all()))

    def test_command_skips_existing_redirects(self) -> None:
        default_site = Site.objects.first()
        assert default_site is not None
        existing_redirect = BUILTIN_REDIRECTS[0]
        PageNotFoundEntry.objects.create(
            site=default_site,
            url=existing_redirect.url,
            regular_expression=existing_redirect.regular_expression,
            is_active=True,
        )

        call_command("import_builtin_redirects", site_id=default_site.id)

        self.assertEqual(
            PageNotFoundEntry.objects.filter(site=default_site).count(),
            len(BUILTIN_REDIRECTS),
        )

    @override_settings(APPEND_SLASH=True)
    def test_respects_append_slash_when_checking_duplicates(self) -> None:
        default_site = Site.objects.first()
        assert default_site is not None
        custom_redirect = BuiltinRedirect(url="/example", regular_expression=False)
        PageNotFoundEntry.objects.create(
            site=default_site,
            url="/example/",
            regular_expression=False,
        )

        result = import_builtin_redirects_for_site(
            default_site,
            redirects=[custom_redirect],
        )

        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped_urls, (custom_redirect.url,))


class CleanRedirectsCommandTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.default_site = Site.objects.first()
        assert self.default_site is not None
        self.default_site.site_name = "Default Site"
        self.default_site.save()

    def test_deletes_only_empty_targets_when_chosen(self) -> None:
        empty_match = PageNotFoundEntry.objects.create(
            site=self.default_site,
            url="/test.php",
            regular_expression=False,
        )
        with_target = PageNotFoundEntry.objects.create(
            site=self.default_site,
            url="/folder/script.php",
            redirect_to_url="/new",
            regular_expression=False,
        )

        with patch("builtins.input", side_effect=["3", "1"]):
            call_command("clean_redirects")

        self.assertFalse(PageNotFoundEntry.objects.filter(id=empty_match.id).exists())
        self.assertTrue(PageNotFoundEntry.objects.filter(id=with_target.id).exists())

    def test_deletes_all_when_option_two(self) -> None:
        entry = PageNotFoundEntry.objects.create(
            site=self.default_site,
            url="/abc/pg_sleep/1",
            regular_expression=False,
        )
        with patch("builtins.input", side_effect=["3", "2"]):
            call_command("clean_redirects")

        self.assertFalse(PageNotFoundEntry.objects.filter(id=entry.id).exists())

    def test_site_prompt_deletes_only_target_site(self) -> None:
        other_site = self.create_site("second.example.com")
        other_site.site_name = "Second Site"
        other_site.save()
        target_entry = PageNotFoundEntry.objects.create(
            site=other_site,
            url="/something.php",
            regular_expression=False,
        )
        keep_entry = PageNotFoundEntry.objects.create(
            site=self.default_site,
            url="/another.php",
            regular_expression=False,
        )

        with patch("builtins.input", side_effect=["2", "3", "2"]):
            call_command("clean_redirects")

        self.assertFalse(PageNotFoundEntry.objects.filter(id=target_entry.id).exists())
        self.assertTrue(PageNotFoundEntry.objects.filter(id=keep_entry.id).exists())

    def test_cancel_on_invalid_site_choice(self) -> None:
        with patch("builtins.input", side_effect=["999"]):
            result = call_command("clean_redirects")
            self.assertEqual(result, "")
