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
    BuiltinRedirect(url=r"^/.*\.py(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.php(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.(jsp|jspx)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.(asp|aspx)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.sql(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.env(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.git(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/\.git(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.svn(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/\.svn(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.aws(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/node_modules/.*", regular_expression=True),
    BuiltinRedirect(url=r".*/phpmyadmin.*", regular_expression=True),
    BuiltinRedirect(url=r".*wp-includes.*", regular_expression=True),
    BuiltinRedirect(url=r".*wp-admin.*", regular_expression=True),
    BuiltinRedirect(url=r".*wp-login.*", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.vscode.*", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.idea.*", regular_expression=True),
    BuiltinRedirect(url=r"^/.*\.DS_Store(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"^/id_rsa(?:\.pub)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r".*(\.\./|\.\.\\).*", regular_expression=True),
    BuiltinRedirect(url=r".*/etc/passwd.*", regular_expression=True),
    BuiltinRedirect(url=r".*\.bak(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(
        url=r"^/(?:backup|db|dump|database|site|www)\.(?:sql|sqlite3?|zip|tar|tgz|gz|7z|bak)(?:\?.*)?$",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*union(?:\s+all)?\s+select.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*(?:'|\")\s*or\s*1\s*=\s*1.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*(?:sleep|benchmark|pg_sleep)\s*\(.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*load_file\s*\(.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*@@(?:version|hostname).*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*information_schema.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*xp_cmdshell.*",
        regular_expression=True,
    ),
    BuiltinRedirect(
        url=r"(?i).*(?:;|%3b)\s*(?:drop|truncate|shutdown|delete)\s+.*",
        regular_expression=True,
    ),
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
