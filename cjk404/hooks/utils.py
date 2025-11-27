from functools import lru_cache

from wagtail.models import Site


@lru_cache(maxsize=1)
def multiple_sites_exist() -> bool:
    return Site.objects.count() > 1
