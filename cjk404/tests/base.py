from __future__ import annotations

from typing import Optional
from typing import Union

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase
from wagtail.models import Page
from wagtail.models import Site

from cjk404.middleware import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.middleware import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.middleware import PageNotFoundRedirectMiddleware
from cjk404.models import PageNotFoundEntry


class BaseCjk404TestCase(TestCase):
    """Shared setup and helpers for cjk404 tests."""

    def setUp(self) -> None:
        super().setUp()
        cache.delete(DJANGO_REGEX_REDIRECTS_CACHE_KEY)
        cache.delete(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY)
        self.request_factory = RequestFactory()
        self.root_page = Page.get_first_root_node()
        if self.root_page is None:
            self.root_page = Page.add_root(instance=Page(title="Root", slug="root"))
        if not Site.objects.exists():
            Site.objects.create(
                hostname="testserver",
                root_page=self.root_page,
                is_default_site=True,
            )

    def create_site(self, hostname: str, *, is_default: bool = False) -> Site:
        return Site.objects.create(
            hostname=hostname,
            root_page=self.root_page,
            is_default_site=is_default,
        )

    def create_redirect(
        self,
        url: str,
        redirect_to_url: Union[str, Page],
        *,
        site: Optional[Site] = None,
        redirect_to_page: Optional[Page] = None,
        is_permanent: bool = False,
        is_regexp: bool = False,
        is_fallback: bool = False,
    ) -> PageNotFoundEntry:
        target_site = site or Site.objects.filter(is_default_site=True).first()
        assert target_site is not None, "A default Site is required for tests."
        return PageNotFoundEntry.objects.create(
            url=url,
            redirect_to_url=redirect_to_url,
            redirect_to_page=redirect_to_page,
            permanent=is_permanent,
            regular_expression=is_regexp,
            fallback_redirect=is_fallback,
            site=target_site,
        )

    def build_middleware(self) -> PageNotFoundRedirectMiddleware:
        return PageNotFoundRedirectMiddleware(lambda request: HttpResponse(status=404))
