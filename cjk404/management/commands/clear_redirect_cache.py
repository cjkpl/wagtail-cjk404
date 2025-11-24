from __future__ import annotations

from typing import Any
from typing import Optional

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from wagtail.models import Site

from cjk404.cache import clear_redirect_caches

SUCCESS = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"


class Command(BaseCommand):

    help = "Clear Cache for Redirects"

    def add_arguments(self, parser) -> None:  # type: ignore[override]
        parser.add_argument(
            "--site-id",
            type=int,
            help="Clear Cache for Redirects",
        )

    def _get_target_site_ids(self, site_id: Optional[int]) -> list[Optional[int]]:
        if site_id is None:
            site_ids: list[Optional[int]] = list(Site.objects.values_list("id", flat=True))
            site_ids.append(None)
            return site_ids
        if not Site.objects.filter(pk=site_id).exists():
            raise CommandError(f"Site with ID={site_id} Not Found")
        return [site_id]

    def handle(self, *args: Any, **options: Any) -> str:
        site_id_option = options.get("site_id")
        site_id: Optional[int] = int(site_id_option) if site_id_option is not None else None
        target_site_ids = self._get_target_site_ids(site_id)
        for current_site_id in target_site_ids:
            clear_redirect_caches(current_site_id)
        if len(target_site_ids) == 1 and target_site_ids[0] is None:
            success_message = "Redirects Cache Cleared"
            colored = f"{SUCCESS}{success_message}{ENDC}"
            self.stdout.write(colored)
            return ""

        site_names: list[str] = []
        for current_site_id in target_site_ids:
            if current_site_id is None:
                continue
            site = Site.objects.filter(pk=current_site_id).first()
            display_name = (
                site.site_name or site.hostname or f"Site {current_site_id}"
                if site
                else f"Site {current_site_id}"
            )
            site_names.append(display_name)

        lines = "\n".join(f"- {name}" for name in site_names)
        success_message = f"Redirects Cache Cleared for Sites:\n{lines}"
        colored = f"{SUCCESS}{success_message}{ENDC}"
        self.stdout.write(colored)
        return ""
