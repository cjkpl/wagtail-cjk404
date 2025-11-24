from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import Union

from django.conf import settings
from django.core.exceptions import ValidationError
from wagtail.models import Site

from cjk404.models import PageNotFoundEntry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BuiltinRedirect:
    url: str
    regular_expression: bool = False


@dataclass(frozen=True, slots=True)
class ImportResult:
    site: Site
    created: int
    skipped_urls: Tuple[str, ...]
    errors: Tuple[str, ...]


BUILTIN_REDIRECTS: Tuple[BuiltinRedirect, ...] = (
    BuiltinRedirect(url=r"^/.*\.php(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r".*pg_sleep.*", regular_expression=True),
    BuiltinRedirect(url=r".*wp-includes.*", regular_expression=True),
)


def _candidate_urls(redirect: BuiltinRedirect, append_slash: bool) -> Set[str]:
    if redirect.regular_expression:
        return {redirect.url}
    return PageNotFoundEntry.build_url_variants(redirect.url, append_slash=append_slash)


def builtin_redirect_status_for_site(
    site: Site,
    *,
    redirects: Sequence[BuiltinRedirect] = BUILTIN_REDIRECTS,
    append_slash: bool | None = None,
) -> Tuple[int, int]:

    effective_append_slash = bool(settings.APPEND_SLASH) if append_slash is None else append_slash
    existing = 0

    for redirect in redirects:
        candidate_urls = _candidate_urls(redirect, append_slash=effective_append_slash)
        queryset = PageNotFoundEntry.objects.filter(site=site, url__in=candidate_urls)
        if redirect.regular_expression:
            queryset = queryset.filter(regular_expression=True)
        else:
            queryset = queryset.filter(regular_expression=False)

        if queryset.exists():
            existing += 1

    return existing, len(redirects)


def import_builtin_redirects_for_site(
    site: Site,
    *,
    redirects: Sequence[BuiltinRedirect] = BUILTIN_REDIRECTS,
    append_slash: bool | None = None,
) -> ImportResult:

    effective_append_slash = bool(settings.APPEND_SLASH) if append_slash is None else append_slash
    created = 0
    skipped: list[str] = []
    errors: list[str] = []

    for redirect in redirects:
        candidate_urls = _candidate_urls(redirect, append_slash=effective_append_slash)
        duplicate_exists = PageNotFoundEntry.objects.filter(
            site=site, url__in=candidate_urls
        ).exists()
        if duplicate_exists:
            skipped.append(redirect.url)
            continue

        try:
            PageNotFoundEntry.objects.create(
                site=site,
                url=redirect.url,
                regular_expression=redirect.regular_expression,
                is_active=False,
            )
        except ValidationError as exc:
            errors.append(f"{redirect.url}: {exc}")
        except Exception as exc:  # pragma: no cover - defensive coding for unexpected issues
            logger.exception(
                "Unexpected error while importing built-in redirect",
                extra={"site_id": site.id, "redirect_url": redirect.url},
            )
            errors.append(f"{redirect.url}: {exc}")
        else:
            created += 1

    return ImportResult(
        site=site,
        created=created,
        skipped_urls=tuple(skipped),
        errors=tuple(errors),
    )
