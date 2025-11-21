from __future__ import annotations

from typing import Iterable
from typing import Optional
from typing import Set
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import formats
from django.utils import timezone
from django.utils.html import format_html
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels import MultiFieldPanel
from wagtail.admin.panels import PageChooserPanel
from wagtail.admin.widgets import SwitchInput
from wagtail.models import Page
from wagtail.models import Site


class PageNotFoundEntry(models.Model):
    site = models.ForeignKey(
        Site,
        related_name="pagenotfound_entries",
        on_delete=models.CASCADE,
        verbose_name="Site",
    )

    url = models.CharField(max_length=1000, verbose_name="Redirect from URL")
    redirect_to_url = models.CharField(
        max_length=400,
        null=True,
        blank=True,
        verbose_name="Redirect to URL",
    )
    redirect_to_page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Redirect to Page",
    )

    created = models.DateTimeField(auto_now_add=True, blank=True, verbose_name="Created")
    last_hit = models.DateTimeField(auto_now_add=True, blank=True, verbose_name="Last Hit")
    hits = models.PositiveIntegerField(default=0, verbose_name="# Hits")
    permanent = models.BooleanField(default=False)
    is_active = models.BooleanField("Is Active?", default=True)

    regular_expression = models.BooleanField(default=False, verbose_name="Regular Expression")

    fallback_redirect = models.BooleanField(
        "Fallback Redirect",
        default=False,
        help_text=(
            "This redirect is only matched after all other redirects have failed to "
            "match.<br>This allows us to define a general 'catch-all' that is only "
            "used as a fallback after more specific redirects have been attempted."
        ),
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("site"),
                FieldPanel("url"),
                FieldPanel("regular_expression"),
            ],
            heading="Old Path / Redirect From",
        ),
        MultiFieldPanel(
            [
                FieldPanel("hits"),
                FieldPanel("is_active", widget=SwitchInput()),
            ],
            heading="Hit stats",
            classname="collapsible",
        ),
        MultiFieldPanel(
            [
                PageChooserPanel("redirect_to_page"),
                FieldPanel("redirect_to_url"),
                FieldPanel("permanent"),
                FieldPanel("fallback_redirect"),
            ],
            heading="New Path / Redirect To",
            classname="collapsible",
        ),
    ]

    @property
    def redirect_to(self) -> Optional[str]:
        if self.redirect_to_page:
            return self.redirect_to_page.url
        return self.redirect_to_url

    def redirect_to_url_link(self) -> str:
        if not self.redirect_to_url:
            return "-"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            self.redirect_to_url,
            self.redirect_to_url,
        )

    def redirect_to_page_link(self) -> str:
        if not self.redirect_to_page:
            return "-"

        try:
            page_url = self.redirect_to_page.url or ""
        except Exception:  # pragma: no cover - Wagtail resolves this dynamically
            page_url = ""

        parsed = urlsplit(page_url) if page_url else None
        path = parsed.path if parsed else ""
        query = f"?{parsed.query}" if parsed and parsed.query else ""
        fragment = f"#{parsed.fragment}" if parsed and parsed.fragment else ""
        path_with_suffix = f"{path}{query}{fragment}"
        netloc = parsed.netloc if parsed else ""

        host_for_display = netloc
        if not host_for_display and self.site_id:
            host_for_display = self.site.hostname or ""
            port = getattr(self.site, "port", None)
            if host_for_display and port and port not in (80, 443):
                host_for_display = f"{host_for_display}:{port}"

        if host_for_display and path_with_suffix:
            display_url = f"{host_for_display}{path_with_suffix}"
        elif host_for_display:
            display_url = host_for_display
        elif path_with_suffix:
            display_url = path_with_suffix
        else:
            display_url = page_url or str(self.redirect_to_page)

        link_url = page_url
        if not link_url:
            if host_for_display:
                scheme = "https://"
                link_url = f"{scheme}{host_for_display}{path_with_suffix}"
            else:
                link_url = path_with_suffix or "#"

        admin_edit_url = reverse("wagtailadmin_pages:edit", args=[self.redirect_to_page.pk])

        return format_html(
            (
                '<div><a href="{link}" target="_blank" rel="noopener noreferrer">{url}</a></div>'
                '<div class="w-text-14 w-text-subtle">'
                '<a class="button button-small button-secondary button--ghost" '
                'href="{admin_link}" target="_blank" rel="noopener noreferrer">'
                "{title}"
                "</a></div>"
            ),
            link=link_url,
            url=display_url,
            admin_link=admin_edit_url,
            title=self.redirect_to_page.title or display_url,
        )

    def formatted_last_viewed(self) -> str:
        if not self.last_hit:
            return "-"

        localized = timezone.localtime(self.last_hit)
        date_str = formats.date_format(localized, "j F Y")
        time_str = formats.time_format(localized, "H:i")
        return f"{date_str} at {time_str}"

    def formatted_created(self) -> str:
        if not self.created:
            return "-"
        localized = timezone.localtime(self.created)
        date_str = formats.date_format(localized, "j F Y")
        time_str = formats.time_format(localized, "H:i")
        return f"{date_str} at {time_str}"

    def website_display(self) -> str:
        if not self.site_id:
            return "-"

        site_name = self.site.site_name or self.site.hostname or "Site"
        hostname = self.site.hostname or "localhost"
        root_page = getattr(self.site, "root_page", None)
        root_url = ""
        if root_page:
            try:
                root_url = root_page.url
            except Exception:  # pragma: no cover - resolved at runtime
                root_url = ""
        if not root_url:
            root_url = getattr(self.site, "root_url", None) or f"https://{hostname}"
        default_suffix = " - Default" if getattr(self.site, "is_default_site", False) else ""

        return format_html(
            '{} (<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>){}',
            site_name,
            root_url,
            hostname,
            default_suffix,
        )

    def active_status_badge(self) -> str:
        label = "Active" if self.is_active else "Inactive"
        icon_name = "check" if self.is_active else "cross"
        icon_class = (
            "icon icon-check default w-text-positive-100"
            if self.is_active
            else "icon icon-cross default w-text-text-error"
        )
        return format_html(
            (
                '<span data-cjk404-active-indicator="{pk}">'
                '<svg class="{icon_class}" aria-hidden="true">'
                '<use href="#icon-{icon_name}"></use>'
                "</svg>"
                '<span class="w-sr-only">{label}</span>'
                "</span>"
            ),
            pk=self.pk,
            icon_class=icon_class,
            icon_name=icon_name,
            label=label,
        )

    def activation_toggle_button(self) -> str:
        if not self.pk:
            return "-"
        action_url = reverse("cjk404-toggle-redirect", args=[self.pk])
        is_active = self.is_active
        label = "Deactivate" if is_active else "Activate"
        active_class = "button button-small button-secondary"
        deactivate_class = "button button-small button-secondary button--destructive"
        button_class = deactivate_class if is_active else active_class
        return format_html(
            (
                '<button type="button" class="{}" '
                'data-cjk404-toggle-url="{}" data-cjk404-target="{}" '
                'data-active="{}" data-activate-label="Activate" '
                'data-deactivate-label="Deactivate" data-activate-class="{}" '
                'data-deactivate-class="{}" data-cjk404-toggle-button="{}">'
                "{}</button>"
            ),
            button_class,
            action_url,
            self.pk,
            str(is_active).lower(),
            active_class,
            deactivate_class,
            self.pk,
            label,
        )

    def __str__(self) -> str:
        return f"{self.url} ---> {self.redirect_to}"

    @staticmethod
    def build_url_variants(url: str, *, append_slash: bool) -> Set[str]:
        """Return URL variants that should be treated as equivalent.

        When APPEND_SLASH is enabled Django will treat ``/foo`` and ``/foo/`` as
        the same path, so we validate those as a single logical URL.
        """
        sanitized = url.strip()
        variants: Set[str] = {sanitized}
        if append_slash:
            stripped = sanitized.rstrip("/")
            if stripped:
                variants.update({stripped, f"{stripped}/"})
            elif sanitized:
                variants.add(sanitized)
        return variants

    def _duplicate_urls_for_site(self) -> models.QuerySet["PageNotFoundEntry"]:
        append_slash = bool(settings.APPEND_SLASH and not self.regular_expression)
        candidate_urls = self.build_url_variants(self.url or "", append_slash=append_slash)

        queryset = PageNotFoundEntry.objects.filter(site=self.site, url__in=candidate_urls)
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)
        return queryset

    def validate_unique(self, exclude: Optional[Iterable[str]] = None) -> None:  # type: ignore[override]
        super().validate_unique(exclude=exclude)
        if not self.site_id or not self.url:
            return

        duplicates_exist = self._duplicate_urls_for_site().exists()
        if duplicates_exist:
            message = (
                "A redirect for this URL already exists for the selected site."
                " With APPEND_SLASH enabled, URLs that only differ by a trailing"
                " slash are considered the same."
            )
            raise ValidationError({"url": message})

    class Meta:
        verbose_name = "redirect"
        verbose_name_plural = "redirects"
        ordering = ("-hits",)
