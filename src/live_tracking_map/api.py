from rest_framework_nested import routers

from display.views import ContestViewSet, ImportFCNavigationTask, NavigationTaskViewSet, ContestantViewSet, \
    ImportFCNavigationTaskTeamId, UserPersonViewSet, TaskViewSet, \
    TaskTestViewSet, AircraftViewSet, ClubViewSet, TeamViewSet, ContestTeamViewSet, ContestantTeamIdViewSet, \
    EditableRouteViewSet, ContestFrontEndViewSet, GetScorecardsViewSet
from django.urls import path, include

router = routers.DefaultRouter()
router.register(r'contestsfrontend', ContestFrontEndViewSet, basename="contestsfrontend")
router.register(r'contests', ContestViewSet, basename="contests")
# router.register(r'navigationtasks', NavigationTaskNestedViewSet, basename="rootnavigationtasks")
# router.register(r'routes', RouteViewSet, basename="routes")

navigation_task_router = routers.NestedSimpleRouter(router, r'contests', lookup="contest")
navigation_task_router.register(r'importnavigationtask', ImportFCNavigationTask, basename="importnavigationtask")
navigation_task_router.register(r'importnavigationtaskteamid', ImportFCNavigationTaskTeamId,
                                basename="importnavigationtaskteamid")
navigation_task_router.register(r'navigationtasks', NavigationTaskViewSet, basename="navigationtasks")
navigation_task_router.register(r'tasks', TaskViewSet, basename="tasks")
navigation_task_router.register(r'tasktests', TaskTestViewSet, basename="tasktests")
navigation_task_router.register(r'contestteams', ContestTeamViewSet, basename='contestteams')

contestant_router = routers.NestedSimpleRouter(navigation_task_router, r'navigationtasks', "navigationtasks",
                                               lookup="navigationtask")
contestant_router.register(r'contestants', ContestantViewSet, basename='contestants')
contestant_router.register(r'contestantsteamid', ContestantTeamIdViewSet, basename='contestantsteamid')

router.register(r'userprofile', UserPersonViewSet, basename="userprofile")
router.register(r'aircraft', AircraftViewSet, basename="aircraft")
router.register(r'clubs', ClubViewSet, basename="clubs")
router.register(r'teams', TeamViewSet, basename="teams")
router.register(r'scorecards', GetScorecardsViewSet, basename="scorecards")
router.register(r'editableroutes', EditableRouteViewSet, basename="editableroutes")
# results_details_router = routers.NestedSimpleRouter(router, r'contestresults', lookup='contest')
# results_details_router.register(r'details', ContestResultsDetailsViewSet, basename="contestresultsdetails")

urlpatters = [
    path('', include(router.urls)),
    path('', include(navigation_task_router.urls)),
    path('', include(contestant_router.urls)),
    # path('', include(results_details_router.urls))
]
