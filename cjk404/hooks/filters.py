from django.db.models import Q
from django_filters import BooleanFilter
from django_filters import DateTimeFromToRangeFilter
from django_filters import ModelChoiceFilter
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.filters import WagtailFilterSet
from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.models import PageNotFoundEntry
from cjk404.hooks.utils import multiple_sites_exist


class PageNotFoundEntryFilterSet(WagtailFilterSet):
    site = ModelChoiceFilter(field_name="site", queryset=Site.objects.all(), label="Website")
    is_active = BooleanFilter(field_name="is_active", label="Is Active?")
    regular_expression = BooleanFilter(field_name="regular_expression", label="Regular Expression")
    builtin_redirect = BooleanFilter(
        label="Is Built-In Redirect?",
        method="filter_builtin_redirect",
    )
    redirect_to_url_present = BooleanFilter(
        label="Is Declared Redirect to URL?",
        method="filter_redirect_to_url_present",
    )
    redirect_to_page_present = BooleanFilter(
        label="Is Declared Redirect to Page?",
        method="filter_redirect_to_page_present",
    )
    last_hit = DateTimeFromToRangeFilter(
        label="Last Accessed Date Range",
        widget=DateRangePickerWidget,
    )
    created = DateTimeFromToRangeFilter(
        label="Created Date Range",
        widget=DateRangePickerWidget,
    )
    updated = DateTimeFromToRangeFilter(
        label="Updated Date Range",
        widget=DateRangePickerWidget,
    )
    permanent = BooleanFilter(field_name="permanent", label="Permanent")
    fallback_redirect = BooleanFilter(
        field_name="fallback_redirect",
        label="Fallback Redirect",
    )

    class Meta:
        model = PageNotFoundEntry
        fields = [
            "site",
            "is_active",
            "regular_expression",
            "builtin_redirect",
            "redirect_to_url_present",
            "redirect_to_page_present",
            "last_hit",
            "created",
            "updated",
            "permanent",
            "fallback_redirect",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not multiple_sites_exist():
            self.filters.pop("site", None)
        elif site_filter := self.filters.get("site"):
            site_filter.label = "Website"

    def filter_redirect_to_url_present(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.exclude(redirect_to_url__isnull=True).exclude(redirect_to_url="")
        return queryset.filter(Q(redirect_to_url__isnull=True) | Q(redirect_to_url=""))

    def filter_redirect_to_page_present(self, queryset, name, value):
        if value is None:
            return queryset
        if value:
            return queryset.exclude(redirect_to_page__isnull=True)
        return queryset.filter(redirect_to_page__isnull=True)

    def filter_builtin_redirect(self, queryset, name, value):
        if value is None:
            return queryset

        builtin_regex_urls = [redirect.url for redirect in BUILTIN_REDIRECTS if redirect.regular_expression]
        builtin_plain_urls = [redirect.url for redirect in BUILTIN_REDIRECTS if not redirect.regular_expression]

        builtin_condition = Q()
        if builtin_regex_urls:
            builtin_condition |= Q(regular_expression=True, url__in=builtin_regex_urls)
        if builtin_plain_urls:
            builtin_condition |= Q(regular_expression=False, url__in=builtin_plain_urls)

        if not builtin_condition:
            return queryset

        if value:
            return queryset.filter(builtin_condition)
        return queryset.exclude(builtin_condition)

