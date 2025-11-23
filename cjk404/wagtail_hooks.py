import pickle
from functools import lru_cache
from typing import List
from typing import Optional

from django.core.cache import cache
from django.db.models import Q
from django.templatetags.static import static
from django.urls import path
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django_filters import BooleanFilter
from django_filters import DateTimeFromToRangeFilter
from wagtail import hooks
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.components import MediaContainer
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.admin.ui.tables import Column
from wagtail.admin.widgets.button import HeaderButton
from wagtail.models import Site
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import CopyView
from wagtail.snippets.views.snippets import CreateView
from wagtail.snippets.views.snippets import EditView
from wagtail.snippets.views.snippets import IndexView
from wagtail.snippets.views.snippets import SnippetViewSet

from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import build_cache_key
from cjk404.models import PageNotFoundEntry
from cjk404.views import clear_redirect_cache_view
from cjk404.views import toggle_redirect_activation_view


@lru_cache(maxsize=1)
def multiple_sites_exist() -> bool:
    return Site.objects.count() > 1


class PageNotFoundEntryFilterSet(WagtailFilterSet):
    last_hit = DateTimeFromToRangeFilter(
        label="Last Viewed Date Range",
        widget=DateRangePickerWidget,
    )
    created = DateTimeFromToRangeFilter(
        label="Created Date Range",
        widget=DateRangePickerWidget,
    )
    redirect_to_url_present = BooleanFilter(
        label="Is Declared Redirect to URL?",
        method="filter_redirect_to_url_present",
    )
    redirect_to_page_present = BooleanFilter(
        label="Is Declared Redirect to Page?",
        method="filter_redirect_to_page_present",
    )

    class Meta:
        model = PageNotFoundEntry
        fields = {
            "permanent": ["exact"],
            "regular_expression": ["exact"],
            "site": ["exact"],
            "fallback_redirect": ["exact"],
            "is_active": ["exact"],
        }

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


class _NoStatusHistoryMixin:
    def get_side_panels(self) -> MediaContainer:
        return MediaContainer([])

    def get_history_url(self) -> None:  # type: ignore[override]
        return None


class PageNotFoundEntryCreateView(_NoStatusHistoryMixin, CreateView):
    pass


class PageNotFoundEntryEditView(_NoStatusHistoryMixin, EditView):
    pass


class PageNotFoundEntryCopyView(_NoStatusHistoryMixin, CopyView):
    pass


class PageNotFoundEntryIndexView(IndexView):
    @property
    def _sites(self) -> List[Site]:
        return list(
            Site.objects.all().only("id", "site_name", "hostname").order_by("site_name", "hostname")
        )

    def _cache_size_mb(self, site_id: Optional[int]) -> float:
        keys = [
            build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id),
            build_cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id),
        ]
        total_bytes = 0
        for key in keys:
            value = cache.get(key)
            if value is None:
                continue
            try:
                total_bytes += len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
            except Exception:
                total_bytes += len(str(value).encode())
        return total_bytes / (1024 * 1024)

    @cached_property
    def header_buttons(self):
        buttons = []
        if self.add_url:
            buttons.append(
                HeaderButton(
                    "Add Redirect",
                    url=self.add_url,
                    icon_name="plus",
                    priority=10,
                )
            )

        sites = self._sites
        if not sites:
            return buttons

        multiple_sites_exist = len(sites) > 1
        for order, site in enumerate(sites, start=1):
            display_name = site.site_name or site.hostname or f"Site {site.id}"
            label = f"Clear Cache for {display_name}" if multiple_sites_exist else "Clear Cache"
            clear_cache_url = reverse("cjk404-clear-redirect-cache")
            if site.id is not None:
                clear_cache_url = f"{clear_cache_url}?site_id={site.id}"

            size_mb = self._cache_size_mb(site.id)
            size_label = f" ({size_mb:.1f} MB)"

            buttons.append(
                HeaderButton(
                    f"{label}{size_label}",
                    url=clear_cache_url,
                    icon_name="cross",
                    priority=1000 + order,
                )
            )

        return buttons


class PageNotFoundEntryViewSet(SnippetViewSet):
    model = PageNotFoundEntry
    icon = "redirect"
    menu_label = "Redirects"
    add_item_label = "Add Redirect"
    add_to_admin_menu = True
    index_view_class = PageNotFoundEntryIndexView
    add_view_class = PageNotFoundEntryCreateView
    edit_view_class = PageNotFoundEntryEditView
    copy_view_class = PageNotFoundEntryCopyView
    list_per_page = 15
    search_fields = ("url", "redirect_to_url")
    filterset_class = PageNotFoundEntryFilterSet

    def _get_list_display(self):
        columns = ["url"]
        if multiple_sites_exist():
            columns.append(
                Column(
                    "website_display",
                    label="Website",
                    accessor="website_display",
                    sort_key="site__site_name",
                )
            )
        columns.extend(
            [
                Column(
                    "active_status_badge",
                    label="Is Active?",
                    accessor="active_status_badge",
                    sort_key="is_active",
                ),
                Column(
                    "activation_toggle_button",
                    label="",
                    accessor="activation_toggle_button",
                ),
                Column("hits", label="Number of Views", sort_key="hits"),
                Column(
                    "redirect_to_url_link",
                    label="Redirect to URL",
                    accessor="redirect_to_url_link",
                ),
                Column(
                    "redirect_to_page_link",
                    label="Redirect to Page",
                    accessor="redirect_to_page_link",
                ),
                BooleanColumn(
                    "regular_expression",
                    label="Regular Expression",
                    sort_key="regular_expression",
                ),
                BooleanColumn("permanent", label="Permanent", sort_key="permanent"),
                BooleanColumn(
                    "fallback_redirect",
                    label="Fallback Redirect",
                    sort_key="fallback_redirect",
                ),
                Column(
                    "formatted_last_viewed",
                    label="Last Viewed",
                    accessor="formatted_last_viewed",
                    sort_key="last_hit",
                ),
                Column(
                    "formatted_created",
                    label="Created Date",
                    accessor="formatted_created",
                    sort_key="created",
                ),
            ]
        )
        return tuple(columns)

    def get_index_view_kwargs(self, **kwargs):
        kwargs["list_display"] = self._get_list_display()
        return super().get_index_view_kwargs(**kwargs)


register_snippet(PageNotFoundEntryViewSet)


@hooks.register("register_admin_urls")
def register_cjk404_admin_urls():
    return [
        path(
            "cjk404/redirects/clear-cache/",
            clear_redirect_cache_view,
            name="cjk404-clear-redirect-cache",
        ),
        path(
            "cjk404/redirects/<int:pk>/toggle/",
            toggle_redirect_activation_view,
            name="cjk404-toggle-redirect",
        ),
    ]


@hooks.register("insert_global_admin_js")
def add_redirect_toggle_js():
    return format_html(
        '<script src="{}"></script>',
        static("cjk404/js/redirect_toggle.js"),
    )
