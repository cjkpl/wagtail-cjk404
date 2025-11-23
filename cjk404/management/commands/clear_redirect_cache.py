from __future__ import annotations

from typing import Any
from typing import Optional

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from wagtail.models import Site

from cjk404.cache import clear_redirect_caches


class Command(BaseCommand):

    help = "Clear Cache for Redirect Lookups"

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument(
            "--site-id",
            type=int,
            help="Clear Cache for Redirect Lookups",
        )

    def _get_target_site_ids(self, site_id: Optional[int]) -> list[Optional[int]]:
        if site_id is None:
            site_ids: list[Optional[int]] = list(Site.objects.values_list("id", flat=True))
            site_ids.append(None)
            return site_ids
        if not Site.objects.filter(pk=site_id).exists():
            raise CommandError(f"Site {site_id} Not Found")
        return [site_id]

    def handle(self, *args: Any, **options: Any) -> str:
        site_id_option = options.get("site_id")
        site_id: Optional[int] = int(site_id_option) if site_id_option is not None else None
        target_site_ids = self._get_target_site_ids(site_id)
        for current_site_id in target_site_ids:
            clear_redirect_caches(current_site_id)
        site_list = ", ".join(
            "none" if current_site_id is None else str(current_site_id)
            for current_site_id in target_site_ids
        )
        success_message = f"Cache for Redirect Lookups Cleared for Sites: {site_list}"
        self.stdout.write(self.style.SUCCESS(success_message))
        return success_message
