from django.template import Template, Context
from .email_templates import WELCOME_EMAIL, CONTEST_CREATION_EMAIL, DELETION_EMAIL, EMAIL_SIGNATURE

HEADER = """
<html><body style='font-family: "Calibri", Arial, sans-serif;'>
"""
FOOTER = """
</body></html>
"""


def render_welcome_email(person: "Person") -> str:
    template = Template(HEADER + WELCOME_EMAIL + EMAIL_SIGNATURE + FOOTER)
    context = Context({"person": person})
    return template.render(context)


def render_contest_creation_email(person: "Person") -> str:
    template = Template(HEADER + CONTEST_CREATION_EMAIL + EMAIL_SIGNATURE + FOOTER)
    context = Context({"person": person})
    return template.render(context)


def render_deletion_email():
    template = Template(HEADER + DELETION_EMAIL + EMAIL_SIGNATURE + FOOTER)
    context = Context()
    return template.render(context)
