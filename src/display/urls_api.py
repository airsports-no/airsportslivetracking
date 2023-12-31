from django.urls import path

from display.views_api import (
    get_running_calculators,
    clear_flight_order_generation_cache,
    generate_navigation_task_orders,
    broadcast_navigation_task_orders,
    get_broadcast_navigation_task_orders_status,
    get_contestant_schedule,
    auto_complete_person_last_name,
    get_country_from_location,
    auto_complete_person_id,
    auto_complete_person_phone,
    auto_complete_person_email,
    auto_complete_person_first_name,
    auto_complete_aeroplane,
    auto_complete_club,
    get_persons_for_signup,
)

urlpatterns = [
    path(
        "navigationtask/<int:pk>/runningcalculators/",
        get_running_calculators,
        name="navigationtask_getrunningcalculators",
    ),
    path(
        "navigationtask/<int:pk>/clearflightordersprogress/",
        clear_flight_order_generation_cache,
        name="navigationtask_clearflightordersprogress",
    ),
    path(
        "navigationtask/<int:pk>/generateflightorders/",
        generate_navigation_task_orders,
        name="navigationtask_generateflightorders",
    ),
    path(
        "navigationtask/<int:pk>/broadcastflightorders/",
        broadcast_navigation_task_orders,
        name="navigationtask_broadcastflightorders",
    ),
    path(
        "navigationtask/<int:pk>/getflightordersstatus/",
        get_broadcast_navigation_task_orders_status,
        name="navigationtask_getflightordersstatus",
    ),
    path(
        "navigationtask/<int:pk>/contestants_timeline_data/",
        get_contestant_schedule,
        name="navigationtask_contestantstimelinedata",
    ),
    path("getcountrycode/", get_country_from_location, name="getcountrycode"),
    path("contestant/autocomplete/id/", auto_complete_person_id, name="autocomplete_id"),
    path("contestant/autocomplete/phone/", auto_complete_person_phone, name="autocomplete_phone"),
    path("contestant/autocomplete/email/", auto_complete_person_email, name="autocomplete_email"),
    path("contestant/autocomplete/firstname/", auto_complete_person_first_name, name="autocomplete_first_name"),
    path("contestant/autocomplete/lastname/", auto_complete_person_last_name, name="autocomplete_last_name"),
    path("aeroplane/autocomplete/registration/", auto_complete_aeroplane, name="autocomplete_aeroplane"),
    path("club/autocomplete/name/", auto_complete_club, name="autocomplete_club"),
    path("person/signuplist/", get_persons_for_signup, name="get_persons_for_signup"),
]