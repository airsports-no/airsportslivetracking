from display.models.navigation_task import NavigationTask


for nt in NavigationTask.objects.all():
    if nt.editable_route:
        nt.refresh_editable_route()
        print(f"Refreshed route for navigation task {nt.id}")
