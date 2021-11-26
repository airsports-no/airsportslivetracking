from django.db import models

# Create your models here.
from django.db import models
from rest_framework.fields import CharField
from wagtail.api import APIField

from wagtail.core.models import Page
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.core.rich_text import expand_db_html


class APIRichTextSerializer(CharField):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return expand_db_html(representation)


class APIRichTextField(APIField):
    def __init__(self, name):
        serializer = APIRichTextSerializer()
        super().__init__(name=name, serializer=serializer)


class BodyPage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

    api_fields = [
        APIRichTextField('body')
    ]
