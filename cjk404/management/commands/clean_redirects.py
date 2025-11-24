from __future__ import annotations

import re
from typing import Dict
from typing import Iterable
from typing import List
from typing import Set
from typing import Tuple

from django.core.management import BaseCommand
from django.core.management import CommandError
from django.db.models import Q
from wagtail.models import Site

from cjk404.builtin_redirects import BUILTIN_REDIRECTS
from cjk404.models import PageNotFoundEntry

SUCCESS = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"
MUTED = "\033[90m"


class Command(BaseCommand):
    help = "Remove Existing Redirects Matching Built-In Regular Expressions Redirects"

    def _matched_ids(
        self,
        pattern: re.Pattern[str],
        queryset: Iterable[PageNotFoundEntry],
    ) -> Tuple[Set[int], Set[int]]:
        with_redirect: Set[int] = set()
        without_redirect: Set[int] = set()
        for entry in queryset:
            if not pattern.match(entry.url or ""):
                continue
            has_target = bool(entry.redirect_to_url or entry.redirect_to_page_id)
            if has_target:
                with_redirect.add(entry.id)
            else:
                without_redirect.add(entry.id)
        return with_redirect, without_redirect

    def _compile_patterns(
        self, patterns: Iterable[str], summary_lines: List[str]
    ) -> List[re.Pattern]:
        compiled: List[re.Pattern[str]] = []
        for pattern_str in patterns:
            try:
                compiled.append(re.compile(pattern_str, re.IGNORECASE))
            except re.error as exc:
                summary_lines.append(f"Skipping Invalid Regular Expressions <{pattern_str}>: {exc}")
        return compiled

    def handle(self, *args, **options) -> str:
        regex_builtins = [redirect for redirect in BUILTIN_REDIRECTS if redirect.regular_expression]

        if not regex_builtins:
            self.stdout.write(f"{WARNING}No Built-In Regular Expressions Redirects Defined{ENDC}")
            return ""

        sites = list(Site.objects.all().order_by("site_name", "hostname", "id"))
        if not sites:
            raise CommandError("No Sites Configured")

        target_site = sites[0]
        if len(sites) > 1:
            prompt_lines = [f"{WARNING}Choose Site to Clean Redirects:{ENDC}"]
            for idx, site in enumerate(sites, start=1):
                name = site.site_name or site.hostname or f"Site {site.id}"
                if getattr(site, "is_default_site", False):
                    name = f"{name} —{SUCCESS} Default{ENDC}"
                display_name = name
                prompt_lines.append(f"{idx}. {display_name}")
            if len(sites) == 2:
                choice_hint = "Enter 1 or 2: "
            else:
                choice_hint = f"Enter 1, 2, or {len(sites)}: "
            prompt_lines.extend(["", choice_hint])
            site_choice = input("\n".join(prompt_lines))
            if not site_choice.isdigit() or not (1 <= int(site_choice) <= len(sites)):
                self.stdout.write(f"{WARNING}Cancelled — No Redirects Deleted{ENDC}")
                return ""
            target_site = sites[int(site_choice) - 1]

        queryset = PageNotFoundEntry.objects.filter(regular_expression=False, site=target_site)

        if not queryset.exists():
            display_name = target_site.site_name or target_site.hostname or f"Site {target_site.id}"
            self.stdout.write(
                f"{WARNING}No Non-Regular Expressions Redirects Found for {display_name}{ENDC}"
            )
            return ""

        summary_lines: List[str] = []
        imported_regex_qs = PageNotFoundEntry.objects.filter(
            regular_expression=True, url__in=[r.url for r in regex_builtins]
        )
        imported_regex_qs = imported_regex_qs.filter(site=target_site)

        pattern_sets = {
            "1": imported_regex_qs.filter(is_active=True).values_list("url", flat=True),
            "2": imported_regex_qs.values_list("url", flat=True),
            "3": [r.url for r in regex_builtins],
        }

        compiled_sets: dict[str, List[re.Pattern[str]]] = {}
        counts: dict[str, int] = {}
        matches_cache: dict[str, Tuple[Set[int], Set[int]]] = {}
        regex_counts = {
            "1": imported_regex_qs.filter(is_active=True).count(),
            "2": imported_regex_qs.count(),
            "3": len(regex_builtins),
        }

        for key, patterns in pattern_sets.items():
            compiled_patterns = self._compile_patterns(patterns, summary_lines)
            compiled_sets[key] = compiled_patterns
            with_ids: Set[int] = set()
            without_ids: Set[int] = set()
            for compiled in compiled_patterns:
                matched_with, matched_without = self._matched_ids(compiled, queryset)
                with_ids.update(matched_with)
                without_ids.update(matched_without)
            matches_cache[key] = (with_ids, without_ids)
            counts[key] = len(with_ids) + len(without_ids)

        selection_prompt = "\n".join(
            [
                "",
                f"{WARNING}Select Built-In Regular Expressions to Consider:{ENDC}",
                (
                    f"1. Imported — Active ({counts.get('1', 0)}) "
                    f"{SUCCESS}— Recommended{ENDC} - {MUTED}{regex_counts.get('1', 0)} RegExp(s){ENDC}"
                ),
                (
                    "2. Imported — Active & Inactive "
                    f"({counts.get('2', 0)}) - {MUTED}{regex_counts.get('2', 0)} RegExp(s){ENDC}"
                ),
                (
                    "3. Imported — Active & Inactive and Not Imported "
                    f"({counts.get('3', 0)}) - {MUTED}{regex_counts.get('3', 0)} RegExp(s){ENDC}"
                ),
                "",
                "Enter 1, 2, or 3: ",
            ]
        )
        choice_scope = input(selection_prompt)

        if choice_scope.strip() not in {"1", "2", "3"}:
            self.stdout.write(f"{WARNING}Cancelled — No Redirects Deleted{ENDC}")
            return ""

        selected_patterns = compiled_sets.get(choice_scope, [])
        deletable_with, deletable_without = matches_cache.get(choice_scope, (set(), set()))

        summary_lines = []
        for pattern in selected_patterns:
            matched_with, matched_without = self._matched_ids(pattern, queryset)
            summary_lines.append(
                (
                    f'Regular Expression "{pattern.pattern}" matches '
                    f"{len(matched_with)} record(s) WITH defined redirection and "
                    f"{len(matched_without)} record(s) WITHOUT defined redirection."
                )
            )

        self.stdout.write("")
        self.stdout.write("\n".join(f"{WARNING}{line}{ENDC}" for line in summary_lines))
        self.stdout.write("")

        if not (deletable_with or deletable_without):
            self.stdout.write(f"{WARNING}No Matching Redirects Found{ENDC}")
            return "\n".join(summary_lines)

        option1_count = len(deletable_without)
        option2_count = len(deletable_with) + len(deletable_without)

        prompt_lines = [
            f"{WARNING}Specify Redirects to Delete:{ENDC}",
            (
                f"1. Redirects with Empty Redirect Definitions ({option1_count}) "
                f"{SUCCESS}— Recommended{ENDC}"
            ),
            f"2. Redirects with Non-Empty & Empty Redirect Definitions ({option2_count})",
            "",
            "Enter 1 or 2: ",
        ]
        choice = input("\n".join(prompt_lines))

        delete_ids: Set[int] = set()
        if choice.strip() == "1":
            delete_ids = deletable_without
        elif choice.strip() == "2":
            delete_ids = deletable_with.union(deletable_without)
        else:
            self.stdout.write(f"{WARNING}Cancelled — No Redirects Deleted{ENDC}")
            return ""

        deleted_count, _ = PageNotFoundEntry.objects.filter(id__in=delete_ids).delete()
        self.stdout.write(f"{SUCCESS}Successfully Deleted {deleted_count} Redirect(s){ENDC}")
        return ""
