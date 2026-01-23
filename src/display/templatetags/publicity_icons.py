# src/display/templatetags/publicity_icons.py
from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()

@register.inclusion_tag('display/publicity_icon.html')
def render_publicity_icon(is_public, is_featured, size=20, class_name=""):
    icon_name = ""
    tooltip_text = ""

    if is_public and is_featured:
        icon_name = "globe"
        tooltip_text = _("Public")
    elif is_public and not is_featured:
        icon_name = "link"
        tooltip_text = _("Unlisted")
    else:
        icon_name = "lock"
        tooltip_text = _("Private")

    return {
        "icon_name": icon_name,
        "size": size,
        "class_name": f"lucide lucide-{icon_name} {class_name}",
        "tooltip_text": tooltip_text
    }
