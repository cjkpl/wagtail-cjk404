from __future__ import annotations

from django.test import override_settings
from wagtail.models import Site

from cjk404.tests.base import BaseCjk404TestCase


@override_settings(ALLOWED_HOSTS=["testserver", "website-a.test", "website-b.test"])
class ExampleRedirectFixturesTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._build_example_fixtures()

    def _build_example_fixtures(self) -> None:
        self.home_a = self.create_and_publish_page(self.root_page, "Home Page", "home-a")
        self.sub_a = self.create_and_publish_page(self.home_a, "Subpage", "sub-a")
        self.home_b = self.create_and_publish_page(self.root_page, "Home Page B", "home-b")
        self.sub_b = self.create_and_publish_page(self.home_b, "Subpage", "sub-b")

        Site.objects.update(is_default_site=False)

        self.site_a = self.create_site(
            "website-a.test",
            is_default=True,
            root_page=self.home_a,
        )
        self.site_b = self.create_site(
            "website-b.test",
            is_default=False,
            root_page=self.home_b,
        )

        self.redirects = [
            self.create_redirect(
                r".*/wp-includes/(.*)",
                "",
                site=self.site_a,
                redirect_to_page=self.home_a,
                is_regexp=True,
                is_permanent=False,
                is_fallback=False,
            ),
            self.create_redirect(
                "/country/(\\w+)(/*)",
                "/countries/profile/$1/",
                site=self.site_a,
                redirect_to_page=None,
                is_regexp=True,
                is_permanent=False,
                is_fallback=False,
            ),
            self.create_redirect(
                "/contact-us/",
                "/contact",
                site=self.site_a,
                is_regexp=False,
                is_permanent=True,
                is_fallback=False,
            ),
            self.create_redirect(
                "/about-us",
                "",
                site=self.site_b,
                redirect_to_page=self.sub_b,
                is_regexp=False,
                is_permanent=False,
                is_fallback=False,
            ),
            self.create_redirect(
                r"/storage/app/media/publications/(.*)\.jpg",
                "/media/images/cover_final.max-600x300.png",
                site=self.site_a,
                is_regexp=True,
                is_permanent=False,
                is_fallback=False,
            ),
            self.create_redirect(
                r"/not-exist/(.*)",
                "/exist/$1",
                site=self.site_b,
                is_regexp=True,
                is_permanent=True,
                is_fallback=False,
            ),
            self.create_redirect(
                r"/not-exist/(.*)",
                "",
                site=self.site_b,
                redirect_to_page=self.sub_b,
                is_regexp=True,
                is_permanent=True,
                is_fallback=True,
            ),
        ]

    def _redirect_for_host(self, path: str, host: str, expected: str, *, status_code: int) -> None:
        response = self.client.get(path, HTTP_HOST=host, follow=False)
        expected_url = expected if expected.startswith("http") else f"http://{host}{expected}"
        self.assertRedirects(
            response,
            expected_url,
            status_code=status_code,
            fetch_redirect_response=False,
        )

    @override_settings(APPEND_SLASH=False)
    def test_regex_to_home_page_site_a(self) -> None:
        self._redirect_for_host(
            "/foo/wp-includes/bar/",
            "website-a.test",
            self.home_a.url,
            status_code=302,
        )

    def test_regex_replacement_to_url_site_a(self) -> None:
        self._redirect_for_host(
            "/country/kenya/",
            "website-a.test",
            "/countries/profile/kenya/",
            status_code=302,
        )

    def test_permanent_redirect_site_a(self) -> None:
        self._redirect_for_host(
            "/contact-us/",
            "website-a.test",
            "/contact",
            status_code=301,
        )

    def test_about_us_to_subpage_site_b(self) -> None:
        self._redirect_for_host(
            "/about-us",
            "website-b.test",
            self.sub_b.url,
            status_code=302,
        )

    def test_jpg_regex_site_a(self) -> None:
        self._redirect_for_host(
            "/storage/app/media/publications/example.jpg",
            "website-a.test",
            "/media/images/cover_final.max-600x300.png",
            status_code=302,
        )

    def test_not_exist_prefers_non_fallback_site_b(self) -> None:
        self._redirect_for_host(
            "/not-exist/abc",
            "website-b.test",
            "/exist/abc",
            status_code=301,
        )

    def test_fallback_entry_present(self) -> None:
        fallback_entries = [r for r in self.redirects if r.fallback_redirect]
        self.assertEqual(len(fallback_entries), 1)
        self.assertEqual(fallback_entries[0].site, self.site_b)
