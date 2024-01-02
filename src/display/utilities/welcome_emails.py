from django.template import Template, Context

from wordpress_facade import get_page, WELCOME_EMAIL_PAGE, EMAIL_SIGNATURE_PAGE, CONTEST_CREATION_EMAIL_PAGE, \
    DELETION_EMAIL_PAGE

HEADER = """
<html><body style='font-family: "Calibri", Arial, sans-serif;'>
"""
FOOTER = """
</body></html>
"""


def render_welcome_email(person: "Person") -> str:
    welcome = get_page(WELCOME_EMAIL_PAGE).get("content", {}).get("rendered", "")
    signature = get_page(EMAIL_SIGNATURE_PAGE).get("content", {}).get("rendered", "")
    template = Template(HEADER + welcome + signature + FOOTER)
    context = Context({"person": person})
    return template.render(context)


def render_contest_creation_email(person: "Person") -> str:
    welcome = get_page(CONTEST_CREATION_EMAIL_PAGE).get("content", {}).get("rendered", "")
    signature = get_page(EMAIL_SIGNATURE_PAGE).get("content", {}).get("rendered", "")
    template = Template(HEADER + welcome + signature + FOOTER)
    context = Context({"person": person})
    return template.render(context)


def render_deletion_email():
    deletion = get_page(DELETION_EMAIL_PAGE).get("content", {}).get("rendered", "")
    signature = get_page(EMAIL_SIGNATURE_PAGE).get("content", {}).get("rendered", "")
    template = Template(HEADER + deletion + signature + FOOTER)
    context = Context()
    return template.render(context)
