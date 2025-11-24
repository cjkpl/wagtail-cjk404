from __future__ import annotations

from typing import Iterable
from typing import List
from typing import Optional

from django.core.management import BaseCommand
from django.core.management import CommandError
from wagtail.models import Site

from cjk404.builtin_redirects import ImportResult
from cjk404.builtin_redirects import import_builtin_redirects_for_site

SUCCESS = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"


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
        return ""

    def _format_results(self, results: Iterable[ImportResult]) -> List[str]:
        lines: List[str] = []
        for result in results:
            site_name = result.site.site_name or result.site.hostname or f"Site {result.site.id}"
            created_line = f"{site_name}: Created {result.created} Redirect(s)"
            lines.append(f"{SUCCESS}{created_line}{ENDC}")
            if result.skipped_urls:
                skipped = f"{site_name}: Skipped {len(result.skipped_urls)} Existing URL(s)"
                lines.append(f"{WARNING}{skipped}{ENDC}")
            if result.errors:
                lines.append(f"{FAIL}Import Errors:{ENDC}")
                lines.extend(
                    f"{FAIL}{index}. {error}{ENDC}"
                    for index, error in enumerate(result.errors, start=1)
                )
        return lines
