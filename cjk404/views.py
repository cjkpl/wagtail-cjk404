from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

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
            "button_html": entry.activation_toggle_button(),
        }
    )
