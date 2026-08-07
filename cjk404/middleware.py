import logging
import re
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import cast

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.db.models import Q
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponsePermanentRedirect
from django.http import HttpResponseRedirect
from django.utils.timezone import now
from wagtail.models import Site

from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
from cjk404.cache import DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT
from cjk404.cache import build_cache_key
from cjk404.models import PageNotFoundEntry

IGNORED_404S = getattr(settings, "IGNORED_404S", [r"^/static/", r"^/favicon.ico"])
logger = logging.getLogger(__name__)


class RedirectDefinition(NamedTuple):
    entry_id: int
    source_url: str
    redirect_to_url: Optional[str]
    redirect_to_page_id: Optional[int]
    permanent: bool


class PageNotFoundRedirectMiddleware:
    def __init__(self, response: Callable[[HttpRequest], HttpResponse]):
        self.response = response
        self.blacklist_url_patterns = [re.compile(string) for string in IGNORED_404S]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        url = request.path
        if self._check_url_in_blacklist(url):
            return self.response(request)
        return self.handle_request(request)

    def _check_url_in_blacklist(self, url: str) -> bool:
        return any(pattern.match(url) for pattern in self.blacklist_url_patterns)

    def update_hit_count(self, entry_id: int) -> None:
        PageNotFoundEntry.objects.filter(id=entry_id).update(
            hits=F("hits") + 1,
            last_hit=now(),
        )

    def host_with_protocol(self, request: HttpRequest) -> str:
        http_host = request.META.get("HTTP_HOST", "")
        if http_host:
            if request.is_secure():
                http_host = f"https://{http_host}"
            else:
                http_host = f"http://{http_host}"
        return http_host

    def HttpRedirect301302(
        self, request: HttpRequest, location: str, is_permanent: bool = False
    ) -> HttpResponse:
        if not location:
            return self.response(request)

        http_host = self.host_with_protocol(request)

        if not (location.startswith("http") or location.startswith("https")):
            location = http_host + location
        if is_permanent:
            return HttpResponsePermanentRedirect(location)
        return HttpResponseRedirect(location)

    def get_redirect_to_page_or_url(self, redirect: RedirectDefinition) -> Optional[str]:
        redirect_to_page_id = redirect.redirect_to_page_id
        if redirect_to_page_id is None:
            return redirect.redirect_to_url
        try:
            entry = PageNotFoundEntry.objects.get(
                redirect_to_page_id=redirect_to_page_id,
                id=redirect.entry_id,
            )
            try:
                page_url = entry.redirect_to_page.url
            except Exception:
                page_url = None
            if page_url:
                return page_url
            fallback_url = entry.redirect_to_url or redirect.redirect_to_url
            return fallback_url
        except PageNotFoundEntry.DoesNotExist:
            return redirect.redirect_to_url

    def _cache_key(self, base_key: str, site_id: Optional[int]) -> str:
        return build_cache_key(base_key, site_id)

    def _get_cached_redirects(
        self,
        *,
        site_id: int,
        regular_expression: bool,
    ) -> list[RedirectDefinition]:
        base_cache_key = (
            DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY
            if regular_expression
            else DJANGO_REGEX_REDIRECTS_CACHE_KEY
        )
        cache_key = self._cache_key(base_cache_key, site_id)
        cached_redirects = cache.get(cache_key)
        if cached_redirects is not None:
            return cast(list[RedirectDefinition], cached_redirects)

        redirect_target_filter = Q(redirect_to_page_id__isnull=False) | (
            Q(redirect_to_url__isnull=False) & ~Q(redirect_to_url="")
        )
        redirect_rows = (
            PageNotFoundEntry.objects.filter(
                site_id=site_id,
                is_active=True,
                regular_expression=regular_expression,
            )
            .filter(redirect_target_filter)
            .order_by("fallback_redirect", "id")
            .values_list(
                "id",
                "url",
                "redirect_to_url",
                "redirect_to_page_id",
                "permanent",
            )
            .iterator(chunk_size=500)
        )
        redirects = [
            RedirectDefinition(
                entry_id=row[0],
                source_url=row[1],
                redirect_to_url=row[2],
                redirect_to_page_id=row[3],
                permanent=row[4],
            )
            for row in redirect_rows
        ]
        cache.set(
            cache_key,
            redirects,
            DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT,
        )
        return redirects

    def _record_not_found(self, site: Site, url: str) -> None:
        url_variants = PageNotFoundEntry.build_url_variants(
            url,
            append_slash=bool(settings.APPEND_SLASH),
        )
        existing_entry = (
            PageNotFoundEntry.objects.filter(site=site, url__in=url_variants)
            .order_by("id")
            .values_list(
                "id",
                "redirect_to_page_id",
                "redirect_to_url",
                "regular_expression",
            )
            .first()
        )
        if existing_entry is not None:
            entry_id, redirect_to_page_id, redirect_to_url, regular_expression = existing_entry
            is_logged_404 = (
                redirect_to_page_id is None and not redirect_to_url and not regular_expression
            )
            if is_logged_404:
                self.update_hit_count(entry_id)
            return
        PageNotFoundEntry.objects.create(site=site, url=url, hits=1)

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        response = self.response(request)
        if response.status_code != 404:
            return response

        url = request.path
        site = Site.find_for_request(request)
        site_id = getattr(site, "pk", None)
        full_path = request.get_full_path()
        max_url_length = getattr(
            settings,
            "CJK404_MAX_REQUEST_URL_LENGTH",
            PageNotFoundEntry._meta.get_field("url").max_length,
        )
        if len(full_path) > max_url_length:
            logger.warning(
                "Blocked Overlong URL Request Path (length=%s, limit=%s, path=%r)",
                len(full_path),
                max_url_length,
                full_path[:256],
            )
            return HttpResponse(status=414)

        if site is None or site_id is None:
            return response

        redirects = self._get_cached_redirects(
            site_id=site_id,
            regular_expression=False,
        )
        exact_urls = {full_path}
        if settings.APPEND_SLASH and not request.path.endswith("/"):
            path_len = len(request.path)
            exact_urls.add(f"{full_path[:path_len]}/{full_path[path_len:]}")
        for redirect in redirects:
            if redirect.source_url not in exact_urls:
                continue
            self.update_hit_count(redirect.entry_id)
            target_redirect_url = self.get_redirect_to_page_or_url(redirect)
            return (
                self.HttpRedirect301302(request, target_redirect_url, redirect.permanent)
                if target_redirect_url
                else response
            )

        regular_expressions_redirects = self._get_cached_redirects(
            site_id=site_id,
            regular_expression=True,
        )
        for redirect in regular_expressions_redirects:
            try:
                old_path = re.compile(redirect.source_url, re.IGNORECASE)
            except re.error:
                continue
            if old_path.match(full_path):
                self.update_hit_count(redirect.entry_id)
                target_redirect_url = self.get_redirect_to_page_or_url(redirect)
                if not target_redirect_url:
                    return response
                new_path = target_redirect_url.replace("$", "\\")
                replaced_path = re.sub(old_path, new_path, full_path)
                return self.HttpRedirect301302(request, replaced_path, redirect.permanent)

        self._record_not_found(site, url)
        return response
