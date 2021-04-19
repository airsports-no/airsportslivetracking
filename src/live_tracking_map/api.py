from rest_framework_nested import routers

from display.views import ContestViewSet, ImportFCNavigationTask, NavigationTaskViewSet, ContestantViewSet, \
    ContestResultsSummaryViewSet, ImportFCNavigationTaskTeamId, UserPersonViewSet, TaskViewSet, \
    TaskTestViewSet
from django.urls import path, include

router = routers.DefaultRouter()
router.register(r'contests', ContestViewSet, basename="contests")
# router.register(r'navigationtasks', NavigationTaskNestedViewSet, basename="rootnavigationtasks")
# router.register(r'routes', RouteViewSet, basename="routes")

navigation_task_router = routers.NestedSimpleRouter(router, r'contests', lookup="contest")
navigation_task_router.register(r'importnavigationtask', ImportFCNavigationTask, basename="importnavigationtask")
navigation_task_router.register(r'importnavigationtaskteamid', ImportFCNavigationTaskTeamId, basename="importnavigationtaskteamid")
navigation_task_router.register(r'navigationtasks', NavigationTaskViewSet, basename="navigationtasks")
navigation_task_router.register(r'tasks', TaskViewSet, basename="tasks")
navigation_task_router.register(r'tasktests', TaskTestViewSet, basename="tasktests")

# Used by results service
router.register(r'contestresults', ContestResultsSummaryViewSet, basename="contestresults")

contestant_router = routers.NestedSimpleRouter(navigation_task_router, r'navigationtasks', "navigationtasks",
                                               lookup="navigationtask")
contestant_router.register(r'contestants', ContestantViewSet, basename='contestants')

router.register(r'userprofile', UserPersonViewSet, basename="userprofile")
# results_details_router = routers.NestedSimpleRouter(router, r'contestresults', lookup='contest')
# results_details_router.register(r'details', ContestResultsDetailsViewSet, basename="contestresultsdetails")

urlpatters = [
    path('', include(router.urls)),
    path('', include(navigation_task_router.urls)),
    path('', include(contestant_router.urls)),
    # path('', include(results_details_router.urls))
]
