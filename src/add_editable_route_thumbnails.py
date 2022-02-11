from django.core.files.base import ContentFile

from display.models import EditableRoute

for e in EditableRoute.objects.all():
    e.thumbnail.save(e.name + "_thumbnail.png",
                     ContentFile(e.create_thumbnail().getvalue()), save=True)
