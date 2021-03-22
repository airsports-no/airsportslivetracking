from django.urls import path
from django.views.generic import TemplateView

from firebase.views import verification_successful

urlpatterns = [
    path("", TemplateView.as_view(template_name="firebase/email_verification.html")),
    path("success", verification_successful, name="verification_successful")
]
