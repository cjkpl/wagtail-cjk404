from __future__ import annotations

from typing import Any
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
    updated = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name="Updated")
    hits = models.PositiveIntegerField(default=0, verbose_name="Number of Views")
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
        FieldPanel("is_active", widget=SwitchInput()),
        MultiFieldPanel(
            [
                FieldPanel("site"),
                FieldPanel("url"),
                FieldPanel("regular_expression", widget=SwitchInput()),
            ],
            heading="Old Path / Redirect From",
        ),
        MultiFieldPanel(
            [
                PageChooserPanel("redirect_to_page"),
                FieldPanel("redirect_to_url"),
                FieldPanel("permanent", widget=SwitchInput()),
                FieldPanel("fallback_redirect", widget=SwitchInput()),
            ],
            heading="New Path / Redirect To",
            classname="collapsible",
        ),
        FieldPanel("hits", heading="Number of Views", read_only=True),
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

        should_truncate = len(display_url) > 35
        short_display = (
            f"{display_url[:35]} .."
            if should_truncate
            else display_url
        )
        truncate_class = "has-full" if should_truncate else ""

        return format_html(
            (
                '<div class="cjk404-url-wrap w-dropdown w-inline-block" '
                'data-controller="w-dropdown">'
                '<a href="{link}" target="_blank" rel="noopener noreferrer" '
                'class="cjk404-url {truncate_class}" title="{full}">'
                '<span class="cjk404-url-short">{short}</span>'
                "</a>"
                '<button type="button" class="w-dropdown__toggle w-dropdown__toggle--icon" '
                'data-w-dropdown-target="toggle" aria-label="Actions">'
                '<svg class="icon icon-dots-horizontal w-dropdown__toggle-icon" aria-hidden="true">'
                '<use href="#icon-dots-horizontal"></use></svg>'
                "</button>"
                '<div class="w-dropdown__content" data-w-dropdown-target="content">'
                '<div class="cjk404-dropdown-box">'
                '<a href="{link}" target="_blank" rel="noopener noreferrer" '
                'class="cjk404-url-full-link cjk404-url" title="{full}">'
                '<svg class="icon icon-expand-right icon" aria-hidden="true">'
                '<use href="#icon-expand-right"></use></svg>'
                '{full}'
                "</a>"
                '<a href="{admin_link}" target="_blank" rel="noopener noreferrer" '
                'class="cjk404-url-full-link" title="Edit in Wagtail">'
                '<svg class="icon icon-site icon" aria-hidden="true">'
                '<use href="#icon-site"></use></svg>'
                'Edit in Wagtail'
                "</a>"
                "</div>"
                "</div>"
                "</div>"
            ),
            link=link_url,
            truncate_class=truncate_class,
            short=short_display,
            full=display_url,
            admin_link=admin_edit_url,
        )

    def formatted_last_viewed(self) -> str:
        if not self.last_hit:
            return "-"

        localized = timezone.localtime(self.last_hit)
        date_str = formats.date_format(localized, "j F Y")
        time_str = formats.time_format(localized, "H:i")
        return f"{date_str} at {time_str}"

    def formatted_updated_date(self) -> str:
        if not self.updated:
            return "-"
        localized = timezone.localtime(self.updated)
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
        default_suffix = ""
        if getattr(self.site, "is_default_site", False):
            default_suffix = format_html(
                ' <svg class="icon icon-pick default" aria-hidden="true" '
                'style="width:1em;height:1em;vertical-align:text-bottom;color:#007d7e;">'
                '<use href="#icon-pick"></use>'
                "</svg>"
                '<span class="w-sr-only">Default site</span>'
            )

        return format_html(
            '{} (<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>){}',
            site_name,
            root_url,
            hostname,
            default_suffix,
        )

    def _toggle_badge(self, field: str, value: bool, true_icon: str, false_icon: str) -> str:
        label = "Yes" if value else "No"
        icon_name = true_icon if value else false_icon
        icon_class = (
            f"icon icon-{true_icon} default w-text-positive-100"
            if value
            else f"icon icon-{false_icon} default w-text-text-error"
        )
        toggle_url = reverse(f"cjk404-toggle-{field}", args=[self.pk]) if self.pk else ""
        target_selector = f"data-cjk404-{field}-indicator"
        return format_html(
            (
                '<span {target}="{pk}" data-cjk404-toggle-url="{toggle_url}" '
                'role="button" tabindex="0" '
                'style="cursor:pointer;transition:opacity 0.2s ease;">'
                '<svg class="{icon_class}" aria-hidden="true">'
                '<use href="#icon-{icon_name}"></use>'
                "</svg>"
                '<span class="w-sr-only">{label}</span>'
                "</span>"
            ),
            target=target_selector,
            pk=self.pk,
            toggle_url=toggle_url,
            icon_class=icon_class,
            icon_name=icon_name,
            label=label,
        )

    def active_status_badge(self) -> str:
        return self._toggle_badge("active", self.is_active, "check", "cross")

    def permanent_status_badge(self) -> str:
        return self._toggle_badge("permanent", self.permanent, "check", "cross")

    def fallback_status_badge(self) -> str:
        return self._toggle_badge("fallback", self.fallback_redirect, "check", "cross")

    def activation_toggle_button(self) -> str:
        return ""

    def __str__(self) -> str:
        return f"{self.url} ---> {self.redirect_to}"

    def url_with_host(self) -> str:
        host = ""
        if self.site_id:
            hostname = self.site.hostname or ""
            port = getattr(self.site, "port", None)
            if hostname:
                host = hostname
                if port and port not in (80, 443):
                    host = f"{hostname}:{port}"
        return f"{host}{self.url}" if host else self.url

    def get_admin_display_title(self) -> str:
        return self.url_with_host()

    @property
    def is_builtin_regex(self) -> bool:
        if not self.regular_expression:
            return False
        from cjk404.builtin_redirects import BUILTIN_REDIRECTS

        return any(
            redirect.regular_expression and redirect.url == self.url for redirect in BUILTIN_REDIRECTS
        )

    @property
    def title_with_host(self) -> str:
        if self.regular_expression:
            base = format_html('<code class="cjk404-code">{}</code>', self.url)
            if self.is_builtin_regex:
                return format_html(
                    '{} <svg class="icon icon-code default" aria-hidden="true" '
                    'style="width:1em;height:1em;vertical-align:text-bottom;color:#007d7e;">'
                    '<use href="#icon-code"></use></svg>'
                    '<span class="w-sr-only">Built-in redirect</span>',
                    base,
                )
            return base

        return self.url_with_host()

    title_with_host.short_description = "Redirect from URL"  # type: ignore[attr-defined]


    def save(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "updated" not in update_fields:
            kwargs["update_fields"] = [*update_fields, "updated"]
        super().save(*args, **kwargs)

    @staticmethod
    def build_url_variants(url: str, *, append_slash: bool) -> Set[str]:
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

    def clean(self) -> None:
        super().clean()
        if self.redirect_to_page and self.redirect_to_url:
            raise ValidationError(
                "Please choose either 'Redirect to Page' or 'Redirect to URL', not both."
            )

    class Meta:
        verbose_name = "redirect"
        verbose_name_plural = "redirects"
        ordering = ("-hits",)
