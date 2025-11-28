from __future__ import annotations

from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.models import PageNotFoundEntry
from cjk404.tests.base import BaseCjk404TestCase
from cjk404.wagtail_hooks import PageNotFoundEntryFilterSet


class BuiltinRedirectFilterTests(BaseCjk404TestCase):
    def setUp(self) -> None:
        super().setUp()
        builtin = BUILTIN_REDIRECTS[0]
        default_site = Site.objects.filter(is_default_site=True).first()
        assert default_site is not None
        self.builtin_entry = PageNotFoundEntry.objects.create(
            site=default_site,
            url=builtin.url,
            redirect_to_url="/builtin-target/",
            regular_expression=builtin.regular_expression,
        )

        self.custom_entry = PageNotFoundEntry.objects.create(
            site=default_site,
            url="/custom/",
            redirect_to_url="/custom-target/",
            regular_expression=False,
        )

    def test_filter_builtin_true(self) -> None:
        filterset = PageNotFoundEntryFilterSet(
            {"builtin_redirect": True},
            queryset=PageNotFoundEntry.objects.all(),
        )
        results = list(filterset.qs)
        self.assertEqual(results, [self.builtin_entry])

    def test_filter_builtin_false(self) -> None:
        filterset = PageNotFoundEntryFilterSet(
            {"builtin_redirect": False},
            queryset=PageNotFoundEntry.objects.all(),
        )
        results = list(filterset.qs)
        self.assertEqual(results, [self.custom_entry])
