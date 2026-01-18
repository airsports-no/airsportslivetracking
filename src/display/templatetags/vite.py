import json
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
import os

register = template.Library()

def get_css_files(manifest, entry, css_files):
    if manifest.get(entry) and 'css' in manifest[entry]:
        for css_path in manifest[entry]['css']:
            css_files.add(os.path.join(settings.STATIC_URL, css_path))
    if manifest.get(entry) and 'imports' in manifest[entry]:
        for imp in manifest[entry]['imports']:
            get_css_files(manifest, imp, css_files)


@register.simple_tag(takes_context=True)
def vite_js(context, path: str, **kwargs):
    manifest_path = os.path.join(settings.BASE_DIR, '..', 'assets_vite', 'manifest.json')
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except FileNotFoundError:
        raise Exception(f"Vite manifest not found at {manifest_path}")

    asset_path = manifest.get(path)

    if not asset_path:
        raise Exception(f"Asset not found in Vite manifest: {path}")

    js_file = os.path.join(settings.STATIC_URL, asset_path['file'])
    
    html = f'<script type="module" src="{js_file}"></script>'

    return mark_safe(html)

@register.simple_tag(takes_context=True)
def vite_css(context, path: str, **kwargs):
    if 'request' not in context:
        raise Exception("request object not found in context. Make sure 'django.template.context_processors.request' is in your an TEMPLATES context_processors.")
        
    request = context['request']
    
    if not hasattr(request, '_vite_css_files'):
        request._vite_css_files = set()

    manifest_path = os.path.join(settings.BASE_DIR, '..', 'assets_vite', 'manifest.json')
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except FileNotFoundError:
        raise Exception(f"Vite manifest not found at {manifest_path}")

    html = ""
    css_files = set()
    get_css_files(manifest, path, css_files)
    
    new_css_files = css_files - request._vite_css_files
    
    for css_file in new_css_files:
        html += f'<link rel="stylesheet" href="{css_file}">'
        request._vite_css_files.add(css_file)

    return mark_safe(html)
