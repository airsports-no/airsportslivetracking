from rest_framework_nested import routers
from django.urls import path, include, reverse
from django.http import JsonResponse
from django.conf import settings
from django_js_reverse.views import urls_json
import json

from display.viewsets import (
    ContestFrontEndViewSet,
    ContestViewSet,
    ImportFCNavigationTask,
    ImportFCNavigationTaskTeamId,
    NavigationTaskViewSet,
    TaskViewSet,
    TaskTestViewSet,
    ContestTeamViewSet,
    ContestantViewSet,
    ContestantTeamIdViewSet,
    UserPersonViewSet,
    AircraftViewSet,
    ClubViewSet,
    TeamViewSet,
    GetScorecardsViewSet,
    EditableRouteViewSet,
)

router = routers.DefaultRouter()
router.register(r"contestsfrontend", ContestFrontEndViewSet, basename="contestsfrontend")
router.register(r"contests", ContestViewSet, basename="contests")
# router.register(r'navigationtasks', NavigationTaskNestedViewSet, basename="rootnavigationtasks")
# router.register(r'routes', RouteViewSet, basename="routes")

navigation_task_router = routers.NestedSimpleRouter(router, r"contests", lookup="contest")
navigation_task_router.register(r"importnavigationtask", ImportFCNavigationTask, basename="importnavigationtask")
navigation_task_router.register(
    r"importnavigationtaskteamid", ImportFCNavigationTaskTeamId, basename="importnavigationtaskteamid"
)
navigation_task_router.register(r"navigationtasks", NavigationTaskViewSet, basename="navigationtasks")
navigation_task_router.register(r"tasks", TaskViewSet, basename="tasks")
navigation_task_router.register(r"tasktests", TaskTestViewSet, basename="tasktests")
navigation_task_router.register(r"contestteams", ContestTeamViewSet, basename="contestteams")

contestant_router = routers.NestedSimpleRouter(
    navigation_task_router, r"navigationtasks", "navigationtasks", lookup="navigationtask"
)
contestant_router.register(r"contestants", ContestantViewSet, basename="contestants")
contestant_router.register(r"contestantsteamid", ContestantTeamIdViewSet, basename="contestantsteamid")

router.register(r"userprofile", UserPersonViewSet, basename="userprofile")
router.register(r"aircraft", AircraftViewSet, basename="aircraft")
router.register(r"clubs", ClubViewSet, basename="clubs")
router.register(r"teams", TeamViewSet, basename="teams")
router.register(r"scorecards", GetScorecardsViewSet, basename="scorecards")
router.register(r"editableroutes", EditableRouteViewSet, basename="editableroutes")
# results_details_router = routers.NestedSimpleRouter(router, r'contestresults', lookup='contest')
# results_details_router.register(r'details', ContestResultsDetailsViewSet, basename="contestresultsdetails")


def frontend_context_view(request):
    user_data = {
        "is_authenticated": request.user.is_authenticated,
        "is_superuser": request.user.is_superuser,
        "is_staff": request.user.is_staff,
        "email": request.user.email if request.user.is_authenticated else None,
        "STATIC_FILE_LOCATION": settings.STATIC_URL,
        "loginLink": reverse("login") + "?next=/",
        "logoutLink": reverse("logout"),
    }
    
    # Get Django reversed URLs from django_js_reverse
    urls_data_response = urls_json(request)
    urls_data = json.loads(urls_data_response.content)

    # Combine user data and URLs
    context_data = {**user_data, "urls": urls_data}
    
    return JsonResponse(context_data)

urlpatters = [
    path("frontend-context/", frontend_context_view, name="frontend-context"),
    path("", include(router.urls)),
    path("", include(navigation_task_router.urls)),
    path("", include(contestant_router.urls)),
    # path('', include(results_details_router.urls))
]
