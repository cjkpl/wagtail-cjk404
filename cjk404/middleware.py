import re
from typing import Any
from typing import Callable
from typing import Mapping
from typing import Optional

from django.conf import settings
from django.core.cache import cache
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
        entry = PageNotFoundEntry.objects.get(id=entry_id)
        entry.hits += 1
        entry.last_hit = now()
        entry.save()

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

    def get_redirect_to_page_or_url(self, redirect: Mapping[str, Any]) -> Optional[str]:
        """For a redirect list element, e.g. retrieved from cache,
        return the target URL, whether it is a page url or raw url,
        or None if neither is found."""

        redirect_to_page_id = redirect.get("redirect_to_page_id")
        if redirect_to_page_id is None:
            # print(
            #     f"redirect_to_page_id is None, returning {redirect['redirect_to_url']}"
            # )
            redirect_to_url = redirect.get("redirect_to_url")
            return str(redirect_to_url) if redirect_to_url else None

        try:
            entry = PageNotFoundEntry.objects.get(
                redirect_to_page_id=redirect_to_page_id, id=redirect["id"]
            )
            return entry.redirect_to_page.url
        except PageNotFoundEntry.DoesNotExist:
            return None

    def _cache_key(self, base_key: str, site_id: Optional[int]) -> str:
        return build_cache_key(base_key, site_id)

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        response = self.response(request)
        if response.status_code != 404:
            return response

        url = request.path
        site = Site.find_for_request(request)
        site_id = getattr(site, "pk", None)

        # find matching url in PageNotFoundEntry, and increase hit count

        full_path = request.get_full_path()

        redirects_cache_key = self._cache_key(DJANGO_REGEX_REDIRECTS_CACHE_KEY, site_id)
        redirects = cache.get(redirects_cache_key)
        if redirects is None:
            base_redirects = PageNotFoundEntry.objects.all()
            if site_id is not None:
                base_redirects = base_redirects.filter(site_id=site_id)
            redirects = list(base_redirects.order_by("fallback_redirect").values())
            cache.set(
                redirects_cache_key,
                redirects,
                DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT,
            )

        # non-regexp to be attempted first (faster)
        for redirect in redirects:

            if redirect["url"] == full_path:
                self.update_hit_count(redirect["id"])

                target_redirect_url = self.get_redirect_to_page_or_url(redirect)
                return (
                    self.HttpRedirect301302(request, target_redirect_url, redirect["permanent"])
                    if target_redirect_url
                    else response
                )

            if settings.APPEND_SLASH and not request.path.endswith("/"):
                path_len = len(request.path)
                slashed_full_path = f"{full_path[:path_len]}/{full_path[path_len:]}"
                # stdout.write(f"SFP: {slashed_full_path}")

                if redirect["url"] == slashed_full_path:
                    self.update_hit_count(redirect["id"])
                    target_redirect_url = self.get_redirect_to_page_or_url(redirect)
                    return (
                        self.HttpRedirect301302(request, target_redirect_url, redirect["permanent"])
                        if target_redirect_url
                        else response
                    )

        # no match found, try regexp
        regex_cache_key = self._cache_key(DJANGO_REGEX_REDIRECTS_CACHE_REGEX_KEY, site_id)
        regular_expressions_redirects = cache.get(regex_cache_key)
        if regular_expressions_redirects is None:
            regex_redirects = PageNotFoundEntry.objects.filter(regular_expression=True)
            if site_id is not None:
                regex_redirects = regex_redirects.filter(site_id=site_id)
            regular_expressions_redirects = list(
                regex_redirects.order_by("fallback_redirect").values()
            )
            cache.set(
                regex_cache_key,
                regular_expressions_redirects,
                DJANGO_REGEX_REDIRECTS_CACHE_TIMEOUT,
            )

        for redirect in regular_expressions_redirects:
            # print(f"Checking {redirect['url']} with {full_path}")
            try:
                old_path = re.compile(redirect["url"], re.IGNORECASE)
                # print(f"Old path: {old_path}")
            except re.error:
                # print(f"Regexp compilation error: {redirect['url']}")
                continue

            if old_path.match(full_path):
                # print(f"Matched {redirect['url']} with {full_path}")

                self.update_hit_count(redirect["id"])

                target_redirect_url = self.get_redirect_to_page_or_url(redirect)
                if not target_redirect_url:
                    # print("No target redirect url found")
                    return response  # no redirect found, return 404

                new_path = target_redirect_url.replace("$", "\\")
                replaced_path = re.sub(old_path, new_path, full_path)
                return self.HttpRedirect301302(request, replaced_path, redirect["permanent"])
            else:
                pass
                # print(f"Not matched {redirect['url']} with {full_path}")

        if (
            response.status_code == 404
            and site
            and not PageNotFoundEntry.objects.filter(
                site=site,
                url__in=PageNotFoundEntry.build_url_variants(
                    url,
                    append_slash=bool(settings.APPEND_SLASH),
                ),
            ).exists()
        ):
            PageNotFoundEntry.objects.create(site=site, url=url, hits=1)
        return response
