from django.conf.urls import url
from django.urls import path
from django.views.generic import TemplateView, RedirectView

from display.views import frontend_view, RetrieveContestApi, import_track

urlpatterns = [
    path('importtrack', import_track, name="import_track"),
    path('frontend/<int:pk>/', frontend_view),
    url(r'frontend/\d+/(?P<path>.*)$', RedirectView.as_view(url='/static/bundles/local/%(path)s')),
    path('api/contest/detail/<int:pk>', RetrieveContestApi.as_view())
]
