import pickle
from functools import lru_cache
from typing import List
from typing import Optional
from typing import Sequence

from django.core.cache import cache
from django.db.models import Q
from django.templatetags.static import static
from django.urls import path
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django_filters import BooleanFilter
from django_filters import DateTimeFromToRangeFilter
from django_filters import ModelChoiceFilter
from wagtail import hooks
from wagtail.admin.filters import DateRangePickerWidget
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.ui.components import Component
from wagtail.admin.ui.components import MediaContainer
from wagtail.admin.ui.menus import MenuItem
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.admin.ui.tables import Column
from wagtail.admin.ui.tables import TitleColumn
from wagtail.admin.widgets.button import BaseButton
from wagtail.admin.widgets.button import Button
from wagtail.admin.widgets.button import ButtonWithDropdown
from wagtail.admin.widgets.button import HeaderButton
from wagtail.models import Site
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import CopyView
from wagtail.snippets.views.snippets import CreateView
from wagtail.snippets.views.snippets import DeleteView
from wagtail.snippets.views.snippets import EditView
from wagtail.snippets.views.snippets import IndexView
from wagtail.snippets.views.snippets import SnippetViewSet

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.builtin_redirects import builtin_redirect_status_for_site
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import build_cache_key
from cjk404.models import PageNotFoundEntry
from cjk404.views import clear_redirect_cache_view
from cjk404.views import import_builtin_redirects_view
from cjk404.views import toggle_redirect_activation_view
from cjk404.views import toggle_redirect_fallback_view
from cjk404.views import toggle_redirect_permanent_view


@lru_cache(maxsize=1)
def multiple_sites_exist() -> bool:
    return Site.objects.count() > 1


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


class PageNotFoundEntryDeleteView(DeleteView):
    view_name = "delete"

    def get_success_message(self):
        return "Redirect(s) Deleted"


class PageNotFoundEntryIndexView(IndexView):
    table_classname = "listing cjk404-listing"

    def get_list_buttons(self, instance):
        next_url = self.request.get_full_path()
        list_buttons = []
        more_buttons = []

        buttons = self.get_list_more_buttons(instance)
        for hook in hooks.get_hooks("register_snippet_listing_buttons"):
            buttons.extend(hook(instance, self.request.user, next_url))

        for button in buttons:
            if isinstance(button, BaseButton) and not button.allow_in_dropdown:
                list_buttons.append(button)
            elif isinstance(button, MenuItem):
                if button.is_shown(self.request.user):
                    more_buttons.append(Button.from_menu_item(button))
            elif button.show:
                more_buttons.append(button)

        for hook in hooks.get_hooks("construct_snippet_listing_buttons"):
            hook(more_buttons, instance, self.request.user)

        if more_buttons:
            list_buttons.append(
                ButtonWithDropdown(
                    buttons=more_buttons,
                    icon_name="dots-horizontal",
                    attrs={
                        "aria-label": "More options",
                    },
                )
            )

        return list_buttons

    def _get_title_column(self, field_name, column_class=TitleColumn, **kwargs):
        if field_name == "__str__":
            kwargs.setdefault("accessor", "title_with_host_display")
            label = "Redirect from URL"
            current_query = self.request.get_full_path()
        else:
            label = None
        column = super()._get_title_column(field_name, column_class, **kwargs)
        if label:
            column.label = label
            column.get_url = lambda obj, _cq=current_query: self.url_helper.get_action_url(
                "edit",
                obj.pk,
                url_params={"next": _cq},
            )
        return column

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
    def header_buttons(self) -> List[Component]:
        buttons: List[Component] = []
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
        action_buttons: List[Button] = []

        for site in sites:
            display_name = site.site_name or site.hostname or f"Site {site.id}"
            existing_count, total_count = builtin_redirect_status_for_site(site)
            import_url = reverse("cjk404-import-builtin-redirects")
            if site.id is not None:
                import_url = f"{import_url}?site_id={site.id}"
            import_label = (
                f"Import Built-in Redirects for {display_name} ({existing_count}/{total_count})"
                if multiple_sites_exist
                else f"Import Built-in Redirects ({existing_count}/{total_count})"
            )

            label = f"Clear Cache for {display_name}" if multiple_sites_exist else "Clear Cache"
            clear_cache_url = reverse("cjk404-clear-redirect-cache")
            if site.id is not None:
                clear_cache_url = f"{clear_cache_url}?site_id={site.id}"

            size_mb = self._cache_size_mb(site.id)
            size_label = f" ({size_mb:.1f} MB)"

            action_buttons.extend(
                [
                    Button(
                        import_label,
                        url=import_url,
                        icon_name="download",
                        priority=10,
                    ),
                    Button(
                        f"{label}{size_label}",
                        url=clear_cache_url,
                        icon_name="cross",
                        priority=20,
                    ),
                ]
            )

        if action_buttons:
            buttons.append(
                self._build_action_dropdown(
                    action_buttons,
                    priority=200,
                )
            )

        return buttons

    def _build_action_dropdown(
        self,
        buttons: Sequence[Button],
        *,
        priority: int,
    ) -> Component:

        return ButtonWithDropdown(
            label="",
            icon_name="dots-horizontal",
            buttons=sorted(buttons),
            priority=priority,
            classname="w-inline-block",
            attrs={"aria-label": "Redirect Actions"},
        )


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
    delete_view_class = PageNotFoundEntryDeleteView
    list_per_page = 15
    search_fields = ("url", "redirect_to_url")
    filterset_class = PageNotFoundEntryFilterSet

    def _get_list_display(self):
        columns = ["__str__"]
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
                    "redirect_to_target_link",
                    label="Redirect to Page or URL",
                    accessor=lambda obj: obj.redirect_to_target_link(),
                ),
                Column(
                    "active_status_badge",
                    label="Is Active?",
                    accessor="active_status_badge",
                    sort_key="is_active",
                ),
                Column("hits", label="Number of Views", sort_key="hits"),
                BooleanColumn(
                    "regular_expression",
                    label="Regular Expression",
                    sort_key="regular_expression",
                ),
                Column(
                    "permanent_status_badge",
                    label="Permanent",
                    accessor="permanent_status_badge",
                    sort_key="permanent",
                ),
                Column(
                    "fallback_status_badge",
                    label="Fallback",
                    accessor="fallback_status_badge",
                    sort_key="fallback_redirect",
                ),
                Column(
                    "formatted_last_viewed",
                    label="Last Accessed Date",
                    accessor="formatted_last_viewed",
                    sort_key="last_hit",
                ),
                Column(
                    "formatted_created",
                    label="Created Date",
                    accessor="formatted_created",
                    sort_key="created",
                ),
                Column(
                    "formatted_updated_date",
                    label="Updated Date",
                    accessor="formatted_updated_date",
                    sort_key="updated",
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
            "cjk404/redirects/import-builtins/",
            import_builtin_redirects_view,
            name="cjk404-import-builtin-redirects",
        ),
        path(
            "cjk404/redirects/<int:pk>/toggle/",
            toggle_redirect_activation_view,
            name="cjk404-toggle-redirect",
        ),
        path(
            "cjk404/redirects/<int:pk>/toggle-active/",
            toggle_redirect_activation_view,
            name="cjk404-toggle-active",
        ),
        path(
            "cjk404/redirects/<int:pk>/toggle-permanent/",
            toggle_redirect_permanent_view,
            name="cjk404-toggle-permanent",
        ),
        path(
            "cjk404/redirects/<int:pk>/toggle-fallback/",
            toggle_redirect_fallback_view,
            name="cjk404-toggle-fallback",
        ),
    ]


@hooks.register("insert_global_admin_js")
def add_redirect_toggle_js():
    return format_html(
        '<script src="{}"></script>',
        static("cjk404/js/redirect_toggle.js"),
    )


@hooks.register("insert_global_admin_css")
def add_cjk404_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("cjk404/css/admin.css"),
    )
