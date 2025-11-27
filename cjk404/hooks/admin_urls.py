from django.templatetags.static import static
from django.urls import path
from django.utils.html import format_html
from wagtail import hooks

from cjk404.views import (
    clear_redirect_cache_view,
    import_builtin_redirects_view,
    toggle_redirect_activation_view,
    toggle_redirect_fallback_view,
    toggle_redirect_permanent_view,
)


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

