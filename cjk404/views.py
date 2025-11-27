from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.core.management import CommandError
from django.core.management import call_command
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from wagtail.admin import messages
from wagtail.models import Site

from cjk404.builtin_redirects import ImportResult
from cjk404.builtin_redirects import import_builtin_redirects_for_site
from cjk404.models import PageNotFoundEntry


@login_required
@permission_required("cjk404.change_pagenotfoundentry", raise_exception=True)
@require_POST
def toggle_redirect_activation_view(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(PageNotFoundEntry, pk=pk)
    entry.is_active = not entry.is_active
    entry.save(update_fields=["is_active"])
    return JsonResponse(
        {
            "ok": True,
            "pk": entry.pk,
            "is_active": entry.is_active,
            "badge_html": entry.active_status_badge(),
            "target_selector": f'[data-cjk404-active-indicator="{entry.pk}"]',
        }
    )


@login_required
@permission_required("cjk404.change_pagenotfoundentry", raise_exception=True)
@require_POST
def toggle_redirect_permanent_view(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(PageNotFoundEntry, pk=pk)
    entry.permanent = not entry.permanent
    entry.save(update_fields=["permanent"])
    return JsonResponse(
        {
            "ok": True,
            "pk": entry.pk,
            "badge_html": entry.permanent_status_badge(),
            "target_selector": f'[data-cjk404-permanent-indicator="{entry.pk}"]',
        }
    )


@login_required
@permission_required("cjk404.change_pagenotfoundentry", raise_exception=True)
@require_POST
def toggle_redirect_fallback_view(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(PageNotFoundEntry, pk=pk)
    entry.fallback_redirect = not entry.fallback_redirect
    entry.save(update_fields=["fallback_redirect"])
    return JsonResponse(
        {
            "ok": True,
            "pk": entry.pk,
            "badge_html": entry.fallback_status_badge(),
            "target_selector": f'[data-cjk404-fallback-indicator="{entry.pk}"]',
        }
    )


@login_required
@permission_required("cjk404.change_pagenotfoundentry", raise_exception=True)
@require_http_methods(["GET", "POST"])
def clear_redirect_cache_view(request: HttpRequest) -> HttpResponse:
    index_url: str = reverse("wagtailsnippets_cjk404_pagenotfoundentry:list")
    site_id_raw = request.POST.get("site_id") or request.GET.get("site_id")
    site_id = None

    if site_id_raw:
        try:
            site_id = int(site_id_raw)
        except (TypeError, ValueError):
            messages.error(request, "Invalid Site ID")
            return redirect(index_url)

    try:
        call_command("clear_redirect_cache", site_id=site_id)
    except CommandError as exc:
        messages.error(request, f"Could Not Clear Redirect Caches: {exc}")
    except Exception as exc:  # pragma: no cover - defensive fallback for unexpected errors
        messages.error(request, f"Clearing Redirect Caches Failed Unexpectedly: {exc}")
    else:
        site_name = "All Sites"
        if site_id is not None:
            site = Site.objects.filter(pk=site_id).first()
            site_name = (
                site.site_name or site.hostname or f"Site {site_id}" if site else f"Site {site_id}"
            )
        messages.success(request, f"Cache for {site_name} Cleared")

    return redirect(index_url)


@login_required
@permission_required("cjk404.add_pagenotfoundentry", raise_exception=True)
@require_http_methods(["GET", "POST"])
def import_builtin_redirects_view(request: HttpRequest) -> HttpResponse:
    index_url: str = reverse("wagtailsnippets_cjk404_pagenotfoundentry:list")
    site_id_raw = request.POST.get("site_id") or request.GET.get("site_id")
    site_id: int | None = None

    if site_id_raw:
        try:
            site_id = int(site_id_raw)
        except (TypeError, ValueError):
            messages.error(request, "Invalid Site ID")
            return redirect(index_url)

    sites_qs = Site.objects.all()
    if site_id is not None:
        sites_qs = sites_qs.filter(pk=site_id)
        if not sites_qs.exists():
            messages.error(request, f"Site with ID={site_id} Not Found")
            return redirect(index_url)

    if not sites_qs.exists():
        messages.error(request, "No Sites Configured — Cannot Import Built-In Redirects")
        return redirect(index_url)

    results: list[ImportResult] = []
    for site in sites_qs:
        try:
            results.append(import_builtin_redirects_for_site(site))
        except Exception as exc:  # pragma: no cover - defensive fallback
            site_name = site.site_name or site.hostname or f"Site {site.pk}"
            messages.error(
                request,
                f"Import Failed for {site_name}: {exc}",
            )

    for result in results:
        site_name = result.site.site_name or result.site.hostname or f"Site {result.site.pk}"
        if result.created:
            messages.success(
                request,
                f"Imported {result.created} Built-In Redirect(s) for {site_name}",
            )
        else:
            messages.success(request, f"No New Built-In Redirects for {site_name}")

        if result.skipped_urls:
            skipped_count = len(result.skipped_urls)
            messages.warning(
                request,
                f"{site_name}: Skipped {skipped_count} Existing URL(s)",
            )

        if result.errors:
            error_lines = [
                f"{index}. {error}" for index, error in enumerate(result.errors, start=1)
            ]
            errors_formatted = "\n".join(error_lines)
            messages.error(request, f"Import Errors:\n{errors_formatted}")

    return redirect(index_url)
