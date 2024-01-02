from guardian.shortcuts import assign_perm

from display.models import UserUploadedMap

for map in UserUploadedMap.objects.all():
    assign_perm("delete_useruploadedmap", map.user, map)
    assign_perm("view_useruploadedmap", map.user, map)
    assign_perm("add_useruploadedmap", map.user, map)
    assign_perm("change_useruploadedmap", map.user, map)