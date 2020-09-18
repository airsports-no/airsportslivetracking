from django.conf.urls import url
from django.urls import path
from django.views.generic import TemplateView, RedirectView

from display.views import frontend_view, RetrieveContestApi, import_track, frontend_view_offline

urlpatterns = [
    path('importtrack', import_track, name="import_track"),
    path('frontend/<int:pk>/', frontend_view),
    path('frontend/offline/<int:pk>/', frontend_view_offline),
    path('api/contest/detail/<int:pk>', RetrieveContestApi.as_view())
]
