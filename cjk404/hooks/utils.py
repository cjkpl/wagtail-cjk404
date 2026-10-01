from wagtail.models import Site


def multiple_sites_exist() -> bool:
    return Site.objects.count() > 1
