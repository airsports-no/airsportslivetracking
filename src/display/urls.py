from django.urls import path

from display.views import import_route, frontend_view_map, \
    GetDataFromTimeForContestant, renew_token, results_service, NewNavigationTaskWizard, NavigationTaskDetailView, \
    ContestantUpdateView, ContestantCreateView, ContestantGateTimesView, ContestCreateView, ContestUpdateView, \
    ContestantDeleteView, ContestDeleteView, NavigationTaskDeleteView, auto_complete_person_phone, \
    auto_complete_person_email

urlpatterns = [
    path('importroute', import_route, name="import_route"),
    path('frontend/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('token/renew', renew_token, name="renewtoken"),
    path('contest/create/', ContestCreateView.as_view(), name="contest_create"),
    path('contest/<int:pk>/update/', ContestUpdateView.as_view(), name="contest_update"),
    path('contest/<int:pk>/delete/', ContestDeleteView.as_view(), name="contest_delete"),
    path('navigationtask/<int:pk>/', NavigationTaskDetailView.as_view(), name="navigationtask_detail"),
    path('navigationtask/<int:pk>/delete/', NavigationTaskDeleteView.as_view(), name="navigationtask_delete"),
    path('contestant/<int:navigationtask_pk>/create/', ContestantCreateView.as_view(), name="contestant_create"),
    path('contestant/<int:pk>/update/', ContestantUpdateView.as_view(), name="contestant_update"),
    path('contestant/<int:pk>/delete/', ContestantDeleteView.as_view(), name="contestant_delete"),
    path('contestant/<int:pk>/gates/', ContestantGateTimesView.as_view(), name="contestant_gate_times"),
    path('contestant/autocomplete/phone/', auto_complete_person_phone, name="autocomplete_phone"),
    path('contestant/autocomplete/email/', auto_complete_person_email, name="autocomplete_email"),
    path('navigationtaskwizard/<int:contest_pk>/', NewNavigationTaskWizard.as_view(), name="navigationtaskwizard")
]
