"""live_tracking_map URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include
from django.views import static
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from display.views import NavigationTaskList

docs = get_schema_view(
    openapi.Info(
        title='Airsports tracking API',
        default_version='v1',
        description="Full API for Airsports tracker",
    ),
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', NavigationTaskList.as_view()),
    path('admin/', admin.site.urls),
    path('display/', include("display.urls")),
    path('accounts/login/', LoginView.as_view(template_name='login.html'), name="login"),
    path('accounts/logout/', LogoutView.as_view(), name="logout"),
    path('docs/', docs.with_ui()),

]
