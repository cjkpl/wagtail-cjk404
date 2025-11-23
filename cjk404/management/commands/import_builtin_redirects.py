from __future__ import annotations

from typing import Iterable
from typing import List
from typing import Optional

from django.core.management import BaseCommand
from django.core.management import CommandError
from wagtail.models import Site

from cjk404.builtin_redirects import ImportResult
from cjk404.builtin_redirects import import_builtin_redirects_for_site


class Command(BaseCommand):
    help = "Import Built-In Redirect Definitions"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--site-id",
            type=int,
            dest="site_id",
            help="Import Built-In Redirect Definitions",
        )

    def handle(self, *args, **options) -> str:
        site_id: Optional[int] = options.get("site_id")
        sites = list(Site.objects.all())
        if not sites:
            raise CommandError("No Configured Sites — Cannot Import Built-In Redirects")
        if site_id is not None:
            sites = [site for site in sites if site.id == site_id]
            if not sites:
                raise CommandError(f"Site with ID={site_id} Not Found")
        results: List[ImportResult] = []
        for site in sites:
            results.append(import_builtin_redirects_for_site(site))
        output_lines = self._format_results(results)
        self.stdout.write("\n".join(output_lines))
        return "\n".join(output_lines)

    def _format_results(self, results: Iterable[ImportResult]) -> List[str]:
        lines: List[str] = []
        for result in results:
            site_name = result.site.site_name or result.site.hostname or f"Site {result.site.id}"
            created_line = f"{site_name}: Created {result.created} Redirect(s)"
            lines.append(created_line)
            if result.skipped_urls:
                skipped = ", ".join(sorted(result.skipped_urls))
                lines.append(f"{site_name}: Skipped Existing URLs: {skipped}")
            if result.errors:
                errors = "; ".join(result.errors)
                lines.append(f"{site_name}: Errors: {errors}")
        return lines
