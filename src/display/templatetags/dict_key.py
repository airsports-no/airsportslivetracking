from django.template.defaultfilters import register


@register.filter(name="dict_key")
def dict_key(d, k):
    return d.get(k)
