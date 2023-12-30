"""
URLs used by the front end
"""
import os

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_tracking_map.settings")
    import django

    django.setup()

from django.urls import reverse


def print_view_url(view_name: str, args: list):
    print(f"{view_name}: {reverse(view_name, args=args)}")


print_view_url("navigationtasks-detail", [1, 2])
print_view_url("navigationtasks-contestant-self-registration", [1, 2])
print_view_url("contestsfrontend-list", [])
print_view_url("contests-list", [])
print_view_url("contests-withdraw", [1])
print_view_url("contests-signup", [1])
print_view_url("contests-team-results-delete", [1])
print_view_url("contests-ongoing-navigation", [])
print_view_url("contests-results", [])
print_view_url("contests-results-details", [1])
print_view_url("contests-update-contest-summary", [1])
print_view_url("contests-update-task-summary", [1])
print_view_url("contests-update-test-result", [1])
print_view_url("tasks-list", [1])
print_view_url("tasks-detail", [1, 2])
print_view_url("tasktests-list", [1])
print_view_url("tasktests-detail", [1, 2])
print_view_url("editableroutes-detail", [1])
print_view_url("editableroute_createnavigationtask", [1])
print_view_url("terms_and_conditions", [])
print_view_url("userprofile-my-participating-contests", [])
print_view_url("contestants-initial-track-data", [1, 2, 3])
print_view_url("contest_details", [1])

print_view_url("aircraft-list", [])
print_view_url("clubs-list", [])
print_view_url("frontend_view_map", [1])
print_view_url("get_persons_for_signup", [])
print_view_url("editableroute_list", [])

print_view_url("autocomplete_aeroplane", [])
print_view_url("autocomplete_club", [])

print_view_url("navigationtask_contestantstimelinedata", [1])
print_view_url("navigationtask_generateflightorders", [1])
print_view_url("navigationtask_broadcastflightorders", [1])
print_view_url("navigationtask_downloadflightorders", [1])
print_view_url("navigationtask_getflightordersstatus", [1])
