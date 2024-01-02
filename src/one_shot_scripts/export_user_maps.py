
"""
Loop through the existing maps in the database and try to infer which local file should be loaded
"""
from display.models import UserUploadedMap


for map in UserUploadedMap.objects.all():
    if not map.map_file.name.startswith("user_uploaded"):
        print(map.map_file.name)
        map.map_file.name=f"user_uploaded_maps/{map.map_file.name}"
        print(len(map.map_file.name))
        map.save()
