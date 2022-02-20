from django.template import Template, Context

from display.wordpress_facade import get_page, WELCOME_EMAIL_PAGE, EMAIL_SIGNATURE_PAGE, CONTEST_CREATION_EMAIL_PAGE


def render_welcome_email(person: "Person") -> str:
    welcome = get_page(WELCOME_EMAIL_PAGE).get("content", {}).get("rendered", "")
    signature = get_page(EMAIL_SIGNATURE_PAGE).get("content", {}).get("rendered", "")
    template = Template(welcome + signature)
    context = Context({"person": person})
    return template.render(context)


def render_contest_creation_email(person: "Person") -> str:
    welcome = get_page(CONTEST_CREATION_EMAIL_PAGE).get("content", {}).get("rendered", "")
    signature = get_page(EMAIL_SIGNATURE_PAGE).get("content", {}).get("rendered", "")
    template = Template(welcome + signature)
    context = Context({"person": person})
    return template.render(context)
