from __future__ import annotations

from typing import Optional

from django.test import override_settings

from cjk404.tests.base import BaseCjk404TestCase


class RedirectTests(BaseCjk404TestCase):
    """
    Behavioural redirect tests.

    Keep one logical assertion per test to avoid cache side-effects.
    """

    def redirect_url(
        self,
        requested_url: str,
        expected_redirect_url: str,
        status_code: Optional[int] = None,
        target_status_code: int = 404,
    ) -> None:
        response = self.client.get(requested_url)
        assert_status = status_code or 302
        self.assertEqual(
            response.status_code,
            assert_status,
            f"Response status code: {response.status_code} != {assert_status}",
        )
        self.assertRedirects(
            response,
            expected_redirect_url,
            status_code=assert_status,
            target_status_code=target_status_code,
        )

    def test_str_representation(self) -> None:
        redirect = self.create_redirect("/initial/", "/new_target/")
        self.assertEqual(str(redirect), "/initial/ ---> /new_target/")

    def test_redirect_increments_hits(self) -> None:
        redirect = self.create_redirect("/initial/", "/new_target/")
        self.assertEqual(redirect.hits, 0)
        self.redirect_url("/initial/", "/new_target/", 302)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_redirect_to_existing_page(self) -> None:
        redirect = self.create_redirect("/initial/", "/", is_permanent=False)
        self.redirect_url("/initial/", "/", 302, 200)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_permanent_redirect(self) -> None:
        redirect = self.create_redirect("/initial2/", "/new_target/", is_permanent=True)
        self.redirect_url("/initial2/", "/new_target/", 301)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_simple_redirect(self) -> None:
        redirect = self.create_redirect("/news/index/b/", "/new_target/")
        self.redirect_url("/news/index/b/", "/new_target/", 302)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    @override_settings(APPEND_SLASH=False)
    def test_regular_expression_without_replacement(self) -> None:
        redirect = self.create_redirect("/news/index/.*/", "/news/boo/b/")
        self.redirect_url("/news/index/.*/", "/news/boo/b/", 302)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_regular_expression_with_replacement_302(self) -> None:
        redirect = self.create_redirect("/news01/index/(.*)/", "/news02/boo/$1/", is_regexp=True)
        self.redirect_url("/news01/index/b/", "/news02/boo/b/", 302, 404)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_regular_expression_with_replacement_301(self) -> None:
        redirect = self.create_redirect(
            "/news03/index/(.*)/", "/news04/boo/$1/", is_permanent=True, is_regexp=True
        )
        self.redirect_url("/news03/index/b/", "/news04/boo/b/", 301, 404)
        redirect.refresh_from_db()
        self.assertEqual(redirect.hits, 1)

    def test_fallback_redirects_ordering(self) -> None:
        """
        Ensure redirects with fallback_redirect set are evaluated last.
        """
        site = self.create_site("fallback.test", is_default=True)

        # Specific redirects
        self.create_redirect("/project/foo/", "/my/project/foo/", site=site)
        self.create_redirect(
            "/project/foo/(.*)/",
            "/my/project/foo/$1/",
            site=site,
            is_regexp=True,
        )
        self.create_redirect(
            "/project/bar/(.*)/",
            "/my/project/bar/$1/",
            site=site,
            is_regexp=True,
        )
        self.create_redirect("/project/bar/", "/my/project/bar/", site=site)

        # Fallback catch-all
        self.create_redirect(
            "/project/(.*)/",
            "/projects/",
            site=site,
            is_regexp=True,
            is_permanent=False,
            is_fallback=True,
        )

        # External hit
        self.create_redirect(
            "/second_project/.*/",
            "http://example.com/my/second_project/bar/",
            site=site,
            is_regexp=True,
        )
        self.create_redirect(
            "/third_project/(.*)/",
            "http://example.com/my/third_project/bar/$1/",
            site=site,
            is_regexp=True,
        )

        self.redirect_url("/project/foo/", "/my/project/foo/", 302, 404)
        self.redirect_url("/project/bar/", "/my/project/bar/", 302, 404)
        self.redirect_url("/project/bar/details/", "/my/project/bar/details/", 302, 404)
        self.redirect_url("/project/foobar/", "/projects/", 302, 404)
        self.redirect_url("/project/foo/details/", "/my/project/foo/details/", 302, 404)

        response = self.client.get("/second_project/details/")
        self.assertRedirects(
            response,
            "http://example.com/my/second_project/bar/",
            status_code=302,
            target_status_code=404,
            fetch_redirect_response=False,
        )

        response = self.client.get("/third_project/details/")
        self.assertRedirects(
            response,
            "http://example.com/my/third_project/bar/details/",
            status_code=302,
            target_status_code=404,
            fetch_redirect_response=False,
        )
