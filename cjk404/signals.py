from __future__ import annotations

from typing import Any
from typing import NamedTuple
from typing import Optional

from django.db import transaction
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver

from cjk404.cache import clear_redirect_caches
from cjk404.models import PageNotFoundEntry

PREVIOUS_CACHE_STATE_ATTRIBUTE = "_cjk404_previous_cache_state"
CACHE_STATE_FIELDS = (
    "site_id",
    "url",
    "redirect_to_url",
    "redirect_to_page_id",
    "permanent",
    "is_active",
    "regular_expression",
    "fallback_redirect",
)


class RedirectCacheState(NamedTuple):
    site_id: Optional[int]
    url: str
    redirect_to_url: Optional[str]
    redirect_to_page_id: Optional[int]
    permanent: bool
    is_active: bool
    regular_expression: bool
    fallback_redirect: bool

    @property
    def is_cacheable(self) -> bool:
        has_target = self.redirect_to_page_id is not None or bool(self.redirect_to_url)
        return self.is_active and has_target


def _cache_state_from_instance(instance: PageNotFoundEntry) -> RedirectCacheState:
    return RedirectCacheState(
        site_id=instance.site_id,
        url=instance.url,
        redirect_to_url=instance.redirect_to_url,
        redirect_to_page_id=instance.redirect_to_page_id,
        permanent=instance.permanent,
        is_active=instance.is_active,
        regular_expression=instance.regular_expression,
        fallback_redirect=instance.fallback_redirect,
    )


def _clear_redirect_caches_after_commit(
    site_id: Optional[int],
    *,
    using: Optional[str],
) -> None:
    transaction.on_commit(lambda: clear_redirect_caches(site_id), using=using)


@receiver(pre_save, sender=PageNotFoundEntry)
def remember_previous_cache_state(
    sender: type[PageNotFoundEntry],
    instance: PageNotFoundEntry,
    raw: bool = False,
    using: str = "default",
    **_: Any,
) -> None:
    previous_state: Optional[RedirectCacheState] = None
    if not raw and instance.pk is not None:
        previous_values = (
            sender.objects.using(using)
            .filter(pk=instance.pk)
            .values_list(*CACHE_STATE_FIELDS)
            .first()
        )
        if previous_values is not None:
            previous_state = RedirectCacheState(*previous_values)
    setattr(instance, PREVIOUS_CACHE_STATE_ATTRIBUTE, previous_state)


@receiver(post_save, sender=PageNotFoundEntry)
def invalidate_redirect_cache_after_save(
    sender: type[PageNotFoundEntry],
    instance: PageNotFoundEntry,
    created: bool,
    raw: bool = False,
    using: str = "default",
    **_: Any,
) -> None:
    del sender
    if raw:
        return

    current_state = _cache_state_from_instance(instance)
    previous_state = getattr(instance, PREVIOUS_CACHE_STATE_ATTRIBUTE, None)
    affected_site_ids: set[Optional[int]] = set()
    if created:
        if current_state.is_cacheable:
            affected_site_ids.add(current_state.site_id)
    elif previous_state == current_state:
        return
    else:
        if previous_state is not None and previous_state.is_cacheable:
            affected_site_ids.add(previous_state.site_id)
        if current_state.is_cacheable:
            affected_site_ids.add(current_state.site_id)

    for site_id in affected_site_ids:
        _clear_redirect_caches_after_commit(site_id, using=using)


@receiver(post_delete, sender=PageNotFoundEntry)
def invalidate_redirect_cache_after_delete(
    sender: type[PageNotFoundEntry],
    instance: PageNotFoundEntry,
    using: str = "default",
    **_: Any,
) -> None:
    del sender
    cache_state = _cache_state_from_instance(instance)
    if cache_state.is_cacheable:
        _clear_redirect_caches_after_commit(cache_state.site_id, using=using)
