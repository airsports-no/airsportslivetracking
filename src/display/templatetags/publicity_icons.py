# src/display/templatetags/publicity_icons.py
from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

register = template.Library()

@register.simple_tag
def render_publicity_icon(is_public, is_featured, size=20, class_name=""):
    status = ""
    icon_svg = ""
    tooltip_text = ""

    if is_public and is_featured:
        status = "Public"
        icon_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-globe {class_name}"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>'
        tooltip_text = _("Public")
    elif is_public and not is_featured:
        status = "Unlisted"
        icon_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-link {class_name}"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07L9.4 11.06A5 5 0 0 0 10 13z"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71A5 5 0 0 0 14 11z"/></svg>'
        tooltip_text = _("Unlisted")
    else:
        status = "Private"
        icon_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-lock {class_name}"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
        tooltip_text = _("Private")

    return mark_safe(f'<div class="tooltip" data-tip="{tooltip_text}">{icon_svg}</div>')