from __future__ import annotations

from typing import List
from typing import Optional
from typing import Sequence

from django.core.management import BaseCommand
from django.core.management import CommandError
from django.db import transaction
from django.db.models import Q
from wagtail.models import Page
from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.models import PageNotFoundEntry

SUCCESS = "\033[92m"
WARNING = "\033[93m"
ENDC = "\033[0m"


class Command(BaseCommand):
    help = (
        "Activate Imported Built-In Redirects"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--site-id",
            type=int,
            dest="site_id",
            help="Activate Imported Built-In Redirects",
        )

    def handle(self, *args, **options) -> str:  # type: ignore[override]
        site_id: Optional[int] = options.get("site_id")
        sites = list(Site.objects.all().order_by("site_name", "hostname", "id"))
        if not sites:
            raise CommandError("No Sites Configured")
        target_site = self._resolve_site(sites, site_id)
        if target_site is None:
            self.stdout.write(f"{WARNING}Cancelled — No Redirects Updated{ENDC}")
            return ""
        builtin_regex_urls = tuple(
            redirect.url for redirect in BUILTIN_REDIRECTS if redirect.regular_expression
        )
        if not builtin_regex_urls:
            self.stdout.write(f"{WARNING}No Built-In Regular Expression Redirects Defined{ENDC}")
            return ""
        queryset = PageNotFoundEntry.objects.filter(
            site=target_site,
            regular_expression=True,
            url__in=builtin_regex_urls,
        )
        if not queryset.exists():
            site_name = self._site_display_name(target_site)
            self.stdout.write(
                f"{WARNING}No Imported Built-In Regular Expressions Found for {site_name}{ENDC}"
            )
            return ""
        target_page = self._get_target_page(target_site)
        update_fields = {"is_active": True, "redirect_to_page": None, "redirect_to_url": "/"}
        target_label = "URL '/'"
        if target_page is not None:
            update_fields.update({"redirect_to_page": target_page, "redirect_to_url": None})
            target_label = f"Root page (ID={target_page.id})"
        updatable_qs = queryset.filter(
            redirect_to_page__isnull=True,
        ).filter(Q(redirect_to_url__isnull=True) | Q(redirect_to_url=""))
        skipped_count = queryset.count() - updatable_qs.count()
        with transaction.atomic():
            updated_count = updatable_qs.update(**update_fields)
        site_name = self._site_display_name(target_site)
        self.stdout.write(
            f"{SUCCESS}Activated {updated_count} Redirect(s) for {site_name}{ENDC}"
        )
        if skipped_count:
            self.stdout.write(
                f"{WARNING}Skipped {skipped_count} Redirect(s) with Defined for {site_name}{ENDC}"
            )
        return ""

    def _resolve_site(
        self, sites: Sequence[Site], site_id: Optional[int]
    ) -> Optional[Site]:
        if site_id is not None:
            matched_site = next((site for site in sites if site.id == site_id), None)
            if matched_site is None:
                raise CommandError(f"Site with ID={site_id} Not Found")
            return matched_site
        if len(sites) == 1:
            return sites[0]
        prompt_lines: List[str] = [f"{WARNING}Choose Site:{ENDC}"]
        for idx, site in enumerate(sites, start=1):
            name = self._site_display_name(site)
            if getattr(site, "is_default_site", False):
                name = f"{name} — {SUCCESS}Default{ENDC}"
            prompt_lines.append(f"{idx}. {name}")
        if len(sites) == 2:
            choice_hint = "Enter 1 or 2: "
        else:
            choice_hint = f"Enter 1-{len(sites)}: "
        prompt_lines.extend(["", choice_hint])
        site_choice = input("\n".join(prompt_lines)).strip()
        if not site_choice.isdigit() or not (1 <= int(site_choice) <= len(sites)):
            return None
        return sites[int(site_choice) - 1]

    def _get_target_page(self, site: Site) -> Optional[Page]:
        try:
            return site.root_page
        except Exception:
            return None

    @staticmethod
    def _site_display_name(site: Site) -> str:
        if site.site_name:
            return site.site_name
        if site.hostname:
            return site.hostname
        if site.id:
            return f"Site {site.id}"
        return "Site"
