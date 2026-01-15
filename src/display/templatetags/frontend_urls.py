from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def fe_url(route_name, **kwargs):
    base_path = "/"
    route_pattern = settings.FRONTEND_ROUTES.get(route_name, "")

    # Prepend the base path if it's not already there
    if route_pattern.startswith("/"):
        path = f"{base_path}{route_pattern[1:]}"
    else:
        path = f"{base_path}{route_pattern}"

    for key, value in kwargs.items():
        path = path.replace(f":{key}", str(value))

    return mark_safe(path)
