from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import override_settings

from cjk404.models import PageNotFoundEntry
from cjk404.tests.base import BaseCjk404TestCase


class UniquenessTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.middleware = self.build_middleware()

    @override_settings(APPEND_SLASH=False)
    def test_duplicate_url_same_site_disallowed_without_append_slash(self) -> None:
        site = self.create_site("site-one.test", is_default=True)
        self.create_redirect("/foo/", "/bar/", site=site)

        duplicate = PageNotFoundEntry(site=site, url="/foo/", redirect_to_url="/baz/")
        with self.assertRaises(ValidationError) as exc:
            duplicate.full_clean()

        self.assertIn("url", exc.exception.message_dict)

    @override_settings(APPEND_SLASH=True)
    def test_trailing_slash_variants_conflict_when_append_slash_enabled(self) -> None:
        site = self.create_site("append.test", is_default=True)
        self.create_redirect("/scholarship-programme/", "/target/", site=site)

        second = PageNotFoundEntry(
            site=site, url="/scholarship-programme", redirect_to_url="/other/"
        )
        with self.assertRaises(ValidationError):
            second.full_clean()

    @override_settings(APPEND_SLASH=False)
    def test_trailing_slash_variants_allowed_when_append_slash_disabled(self) -> None:
        site = self.create_site("no-append.test", is_default=True)
        first = self.create_redirect("/path", "/one/", site=site)
        second = PageNotFoundEntry(site=site, url="/path/", redirect_to_url="/two/")

        # Should validate and save because APPEND_SLASH=False
        second.full_clean()
        second.save()

        urls = set(site.pagenotfound_entries.values_list("url", flat=True))
        self.assertEqual(urls, {"/path", "/path/"})
        self.assertTrue(site.pagenotfound_entries.filter(pk=first.pk).exists())

    @override_settings(APPEND_SLASH=True)
    def test_same_url_allowed_on_different_sites_even_with_append_slash(self) -> None:
        site_one = self.create_site("one.test", is_default=True)
        site_two = self.create_site("two.test")

        entry_one = self.create_redirect("/shared/", "/one/", site=site_one)
        entry_two = PageNotFoundEntry(site=site_two, url="/shared/", redirect_to_url="/two/")
        entry_two.full_clean()
        entry_two.save()

        self.assertNotEqual(entry_one.site_id, entry_two.site_id)
        self.assertEqual(
            set(
                site_one.pagenotfound_entries.values_list("url", flat=True)
            ),  # only one entry for site_one
            {"/shared/"},
        )
        self.assertEqual(
            set(site_two.pagenotfound_entries.values_list("url", flat=True)), {"/shared/"}
        )

    @override_settings(APPEND_SLASH=True)
    def test_middleware_does_not_create_duplicate_variant_on_append_slash(self) -> None:
        site = self.create_site("testserver", is_default=True)
        self.create_redirect("/append-only/", "/target/", site=site)

        request = self.request_factory.get("/append-only", HTTP_HOST=site.hostname)
        self.middleware(request)

        urls = set(site.pagenotfound_entries.values_list("url", flat=True))
        self.assertEqual(urls, {"/append-only/"})
