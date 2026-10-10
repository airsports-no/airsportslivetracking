from django.urls import path
from django.views.decorators.cache import cache_page

from display.views_api import (
    get_running_calculators,
    clear_flight_order_generation_cache,
    generate_navigation_task_orders,
    broadcast_navigation_task_orders,
    get_broadcast_navigation_task_orders_status,
    get_contestant_schedule,
    get_country_from_location,
    auto_complete_aeroplane,
    auto_complete_club,
    search_people,
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
    path("getcountrycode/", get_country_from_location, name="getcountrycode"),
    path("aeroplane/autocomplete/registration/", auto_complete_aeroplane, name="autocomplete_aeroplane"),
    path("club/autocomplete/name/", auto_complete_club, name="autocomplete_club"),
    path("people/search/", search_people, name="people_search"),
]
