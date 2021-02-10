from django.urls import path
from django.views.generic import TemplateView

from display.views import import_route, frontend_view_map, \
    GetDataFromTimeForContestant, renew_token, results_service, NewNavigationTaskWizard, NavigationTaskDetailView, \
    ContestantUpdateView, ContestantCreateView, ContestantGateTimesView, ContestCreateView, ContestUpdateView, \
    ContestantDeleteView, ContestDeleteView, NavigationTaskDeleteView, auto_complete_person_phone, \
    auto_complete_person_email, auto_complete_person_first_name, auto_complete_person_last_name, \
    auto_complete_club, auto_complete_aeroplane, RegisterTeamWizard, ContestTeamList, remove_team_from_contest, \
    TeamUpdateView, auto_complete_person_id, PersonUpdateView, PersonList, NavigationTaskUpdateView, \
    ContestTeamTrackingUpdate, manifest, auto_complete_contestteam_pk, \
    tracking_qr_code_view, get_contestant_map, get_navigation_task_map, add_contest_teams_to_navigation_task, \
    clear_future_contestants, render_contestants_timeline, get_contestant_schedule, global_map, signup_verify

urlpatterns = [
    path('importroute', import_route, name="import_route"),
    path('frontend/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('accounts/signup/verify', signup_verify, name ="signup_verify"),
    path('token/renew', renew_token, name="renewtoken"),
    path('contest/create/', ContestCreateView.as_view(), name="contest_create"),
    path('contest/<int:pk>/update/', ContestUpdateView.as_view(), name="contest_update"),
    path('contest/<int:pk>/delete/', ContestDeleteView.as_view(), name="contest_delete"),
    path('navigationtask/<int:pk>/', NavigationTaskDetailView.as_view(), name="navigationtask_detail"),
    path('navigationtask/<int:pk>/qr/', tracking_qr_code_view, name="navigationtask_qr"),
    path('navigationtask/<int:pk>/map/', get_navigation_task_map, name="navigationtask_map"),
    path('navigationtask/<int:pk>/update/', NavigationTaskUpdateView.as_view(), name="navigationtask_update"),
    path('navigationtask/<int:pk>/delete/', NavigationTaskDeleteView.as_view(), name="navigationtask_delete"),
    path('navigationtask/<int:pk>/add_contestants/', add_contest_teams_to_navigation_task, name="navigationtask_addcontestants"),
    path('navigationtask/<int:pk>/remove_contestants/', clear_future_contestants, name="navigationtask_removecontestants"),
    path('navigationtask/<int:pk>/contestants_timeline/', render_contestants_timeline, name="navigationtask_contestantstimeline"),
    path('navigationtask/<int:pk>/contestants_timeline_data/', get_contestant_schedule, name="navigationtask_contestantstimelinedata"),
    # path('navigationtask/<int:pk>/scoreoverride/', BasicScoreOverrideUpdateView.as_view(),
    #      name="navigationtask_scoreoverride"),
    path('contestant/<int:navigationtask_pk>/create/', ContestantCreateView.as_view(), name="contestant_create"),
    path('contestant/<int:pk>/map/', get_contestant_map, name="contestant_map"),
    path('contestant/<int:pk>/update/', ContestantUpdateView.as_view(), name="contestant_update"),
    path('contestant/<int:pk>/delete/', ContestantDeleteView.as_view(), name="contestant_delete"),
    path('contestant/<int:pk>/gates/', ContestantGateTimesView.as_view(), name="contestant_gate_times"),
    path('contest/<int:contest_pk>/team/<int:team_pk>/wizardupdate/', RegisterTeamWizard.as_view(), name="team_wizard"),
    path('contest/<int:contest_pk>/team/<int:team_pk>/remove/', remove_team_from_contest, name="remove_team"),
    path('contest/<int:contest_pk>/team/create/', RegisterTeamWizard.as_view(), name="create_team"),
    path('contest/<int:contest_pk>/team/<int:pk>/update', TeamUpdateView.as_view(), name="team_update"),
    path('contest/<int:contest_pk>/contestteamtracking/<int:pk>/update', ContestTeamTrackingUpdate.as_view(),
         name="contestteamtracking_update"),
    path('contest/<int:contest_pk>/teams/', ContestTeamList.as_view(), name="contest_team_list"),
    path('contestant/autocomplete/id/', auto_complete_person_id, name="autocomplete_id"),
    path('contestant/autocomplete/phone/', auto_complete_person_phone, name="autocomplete_phone"),
    path('contestant/autocomplete/email/', auto_complete_person_email, name="autocomplete_email"),
    path('contestant/autocomplete/firstname/', auto_complete_person_first_name, name="autocomplete_first_name"),
    path('contestant/autocomplete/lastname/', auto_complete_person_last_name, name="autocomplete_last_name"),
    path('aeroplane/autocomplete/registration/', auto_complete_aeroplane, name="autocomplete_aeroplane"),
    path('club/autocomplete/name/', auto_complete_club, name="autocomplete_club"),
    path('contestteam/autocomplete/pk/', auto_complete_contestteam_pk, name="autocomplete_team_pk"),
    path('navigationtaskwizard/<int:contest_pk>/', NewNavigationTaskWizard.as_view(), name="navigationtaskwizard"),
    path('person/<int:pk>/update/', PersonUpdateView.as_view(), name="person_update"),
    path('person/', PersonList.as_view(), name="person_list"),
    path('manifest/', manifest, name="tracking_manifest")
]
