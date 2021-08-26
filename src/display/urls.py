from django.urls import path
from django.views.generic import TemplateView

from display.views import frontend_view_map, \
    renew_token, results_service, NewNavigationTaskWizard, NavigationTaskDetailView, \
    ContestantUpdateView, ContestantCreateView, ContestantGateTimesView, ContestCreateView, ContestUpdateView, \
    ContestantDeleteView, ContestDeleteView, NavigationTaskDeleteView, auto_complete_person_phone, \
    auto_complete_person_email, auto_complete_person_first_name, auto_complete_person_last_name, \
    auto_complete_club, auto_complete_aeroplane, RegisterTeamWizard, ContestTeamList, remove_team_from_contest, \
    TeamUpdateView, auto_complete_person_id, PersonUpdateView, PersonList, NavigationTaskUpdateView, \
    ContestTeamTrackingUpdate, manifest, \
    tracking_qr_code_view, get_contestant_map, get_navigation_task_map, add_contest_teams_to_navigation_task, \
    clear_future_contestants, render_contestants_timeline, get_contestant_schedule, global_map, ContestDetailView, \
    list_contest_permissions, add_user_contest_permissions, delete_user_contest_permissions, \
    change_user_contest_permissions, contestant_cards_list, contestant_card_remove, create_route_test, \
    clear_results_service, delete_score_item, \
    terminate_contestant_calculator, view_navigation_task_rules, get_contestant_rules, frontend_playback_map, \
    share_contest, share_navigation_task, get_persons_for_signup, get_contestant_default_map, \
    get_contestant_email_flight_orders_link, EditableRouteList, EditableRouteDeleteView, \
    refresh_editable_route_navigation_task, \
    get_contestant_email_flying_orders_link, broadcast_navigation_task_orders, upload_gpx_track_for_contesant

urlpatterns = [
    path('task/<int:pk>/map/', frontend_view_map, name="frontend_view_map"),
    path('task/<int:pk>/playbackmap/', frontend_playback_map, name="frontend_playback_map"),
    path('token/renew', renew_token, name="renewtoken"),
    path('contest/create/', ContestCreateView.as_view(), name="contest_create"),
    path('contest/<int:pk>/', ContestDetailView.as_view(), name="contest_details"),
    path('contest/<int:pk>/clear_results/', clear_results_service, name="contest_clear_results"),
    path('contest/<int:pk>/permissions/', list_contest_permissions, name="contest_permissions_list"),
    path('contest/<int:pk>/permissions/add/', add_user_contest_permissions, name="contest_permissions_add"),
    path('contest/<int:pk>/permissions/<int:user_pk>/change/', change_user_contest_permissions,
         name="contest_permissions_change"),
    path('contest/<int:pk>/permissions/<int:user_pk>/delete', delete_user_contest_permissions,
         name="contest_permissions_delete"),
    path('contest/<int:pk>/create_route/', create_route_test, name="create_route"),
    path('contest/<int:pk>/delete/', ContestDeleteView.as_view(), name="contest_delete"),
    path('contest/<int:pk>/update/', ContestUpdateView.as_view(), name="contest_update"),
    path('contest/<int:pk>/share/', share_contest, name="contest_share"),
    path('navigationtask/<int:pk>/', NavigationTaskDetailView.as_view(), name="navigationtask_detail"),
    path('navigationtask/<int:pk>/qr/', tracking_qr_code_view, name="navigationtask_qr"),
    path('navigationtask/<int:pk>/map/', get_navigation_task_map, name="navigationtask_map"),
    path('navigationtask/<int:pk>/rules/', view_navigation_task_rules, name="navigationtask_rules"),
    path('navigationtask/<int:pk>/update/', NavigationTaskUpdateView.as_view(), name="navigationtask_update"),
    path('navigationtask/<int:pk>/delete/', NavigationTaskDeleteView.as_view(), name="navigationtask_delete"),
    path('navigationtask/<int:pk>/share/', share_navigation_task, name="navigationtask_share"),
    path('navigationtask/<int:pk>/broadcastflightorders/', broadcast_navigation_task_orders,
         name="navigationtask_broadcastflightorders"),

    path('navigationtask/<int:pk>/refresheditableroute/', refresh_editable_route_navigation_task,
         name="navigationtask_refresheditableroute"),
    path('navigationtask/<int:pk>/add_contestants/', add_contest_teams_to_navigation_task,
         name="navigationtask_addcontestants"),
    path('navigationtask/<int:pk>/remove_contestants/', clear_future_contestants,
         name="navigationtask_removecontestants"),
    path('navigationtask/<int:pk>/contestants_timeline/', render_contestants_timeline,
         name="navigationtask_contestantstimeline"),
    path('navigationtask/<int:pk>/contestants_timeline_data/', get_contestant_schedule,
         name="navigationtask_contestantstimelinedata"),
    # path('navigationtask/<int:pk>/scoreoverride/', BasicScoreOverrideUpdateView.as_view(),
    #      name="navigationtask_scoreoverride"),
    path('maplink/<uuid:key>/', get_contestant_email_flight_orders_link, name='email_map_link'),
    path('mapreport/<int:pk>/', get_contestant_email_flying_orders_link, name='email_report_link'),
    path('contestant/<int:navigationtask_pk>/create/', ContestantCreateView.as_view(), name="contestant_create"),
    path('contestant/<int:pk>/map/', get_contestant_map, name="contestant_map"),
    path('contestant/<int:pk>/defaultmap/', get_contestant_default_map, name="contestant_default_map"),
    path('contestant/<int:pk>/rules/', get_contestant_rules, name="contestant_rules"),
    path('contestant/<int:pk>/stop_calculator/', terminate_contestant_calculator, name="contestant_stop_calculator"),
    path('contestant/<int:pk>/list_cards/', contestant_cards_list, name="contestant_cards_list"),
    path('contestant/<int:pk>/remove_card/<int:card_pk>/', contestant_card_remove, name="contestant_card_remove"),
    path('contestant/<int:pk>/update/', ContestantUpdateView.as_view(), name="contestant_update"),
    path('contestant/<int:pk>/delete/', ContestantDeleteView.as_view(), name="contestant_delete"),
    path('contestant/<int:pk>/uploadgpxtrack/', upload_gpx_track_for_contesant, name="contestant_uploadgpxtrack"),
    # path('contestant/<int:pk>/downloadgpxtrack/', download_gpx_track_for_contesant, name="contestant_downloadgpxtrack"),
    path('contestant/remove_score_item/<int:pk>/', delete_score_item, name="contestant_remove_score_item"),
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
    path('navigationtaskwizard/<int:contest_pk>/', NewNavigationTaskWizard.as_view(), name="navigationtaskwizard"),
    path('person/<int:pk>/update/', PersonUpdateView.as_view(), name="person_update"),
    path('person/signuplist/', get_persons_for_signup, name="get_persons_for_signup"),
    path('person/', PersonList.as_view(), name="person_list"),
    path('manifest/', manifest, name="tracking_manifest"),
    path('editableroute/', EditableRouteList.as_view(), name="editableroute_list"),
    path('editableroute/<int:pk>/delete/', EditableRouteDeleteView.as_view(), name="editableroute_delete"),
]
