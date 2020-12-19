from django.template.defaultfilters import register


@register.filter(name="gate_time_offset")
def dict_key(contestant, gate_name):
    offset = contestant.get_gate_time_offset(gate_name)
    if offset is not None:
        return int(offset)
    return "--"
