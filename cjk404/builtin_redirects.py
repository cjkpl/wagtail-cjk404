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
    BuiltinRedirect(url=r"(?i)^/\.(?:git|svn|hg)(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.ssh(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.aws(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.github(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.?(?:DS_Store)(?:\.[A-Za-z0-9._-]+)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.bash_history(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*(?:\.vscode|\.idea)(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/node_modules/.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/(?:Dockerfile|docker-compose(?:\.[A-Za-z0-9._-]+)?\.ya?ml|\.dockerignore)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.docker(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.github/dependabot\.ya?ml(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+config/(?:settings|secrets)\.json(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+config/.*\.conf(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+.*php\.ini(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+php_errors\.log(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/id_rsa(?:\.pub)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.env(?:\.[A-Za-z0-9._-]+)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.log(?:\.[0-9]+)?(?:\.(?:zip|gz|tgz|bz2|xz|zst))?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.sql(?:\.(?:zip|gz|tgz|bz2|xz|zst|7z|rar))*(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.(?:db|sqlite3?|sqlitedb)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/\.?(?:backup|db|dump|database|site|www)\."r"(?:sql|sqlite3?|zip|tar|tgz|gz|bz2|xz|zst|7z|bak|rar)"r"(?:\.[A-Za-z0-9._-]+)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.(?:zip|tar|tgz|gz|bz2|xz|zst|7z|rar)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\bsql\b.*\.jar(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.jar(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+.*\.ph(?:p\d*|p)([^/]*)(?:/.*)?(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.(?:jspx?|aspx?)(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/.*\.py(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*wp-(?:includes|admin|content).*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*/xmlrpc\.php(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*/phpmyadmin.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*(?:\.\./|\.\.\\|%2e%2e%2f|%2e%2e\\|%5c\.\.%5c|%252e%252e%252f|%255c%255c).*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*etc/passwd.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*union(?:\s+all)?\s+select.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*(?:'|\")\s*or\s*1\s*=\s*1\b.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*(?:sleep|benchmark|pg_sleep)\s*\(.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*load_file\s*\(.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*@@(?:version|hostname)\b.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*information_schema\b.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*xp_cmdshell\b.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i).*(?:;|%3b)\s*(?:drop|truncate|shutdown|delete)\s+.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/cgi-bin/.*", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/server-status(?:\?.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+aws/(?:cognito|ecs)(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+aws/ecs/task-credentials(?:/.*)?$", regular_expression=True),
    BuiltinRedirect(url=r"(?i)^/+aws/.+\.(?:json|ya?ml)(?:\?.*)?$", regular_expression=True),
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
                "Unexpected Error Occurred",
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
