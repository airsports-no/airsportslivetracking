from django.contrib import admin

# Register your models here.
from display.models import Contest, Track, Aeroplane, Team, Contestant

admin.site.register(Contest)
admin.site.register(Track)
admin.site.register(Aeroplane)
admin.site.register(Team)
admin.site.register(Contestant)
