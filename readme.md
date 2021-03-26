# Installation guide
1. Clone the repository ("Get code" near the upper right hand corner, using  GitHub is fine)
2. Install docker and docker-compose on your preferred operating system (https://hub.docker.com/editions/community/docker-ce-desktop-windows/)
2. Download raster maps from https://drive.google.com/drive/folders/1068gCZ6RhCijCU0CsAIHXznLyedD9qZZ?usp=sharing
3. Extract the files into the relevant map folders into the subfolder "mapserver" inside the project. Note that the map for the names 
must be exactly the same as from the supported list. Currently supported maps are:
  1. m517_bergen
  2. Norway_N250
3. The resulting folder structure inside the mapserver folder should look like this:
![Map folder structure](https://github.com/kolaf/live_tracking/blob/master/map_directory_structure.png "Map folder structure")
3. Enter the folder with the downloaded project (folder should contain the file docker-compose-dev.yml)
4. Run the project: docker-compose -f docker-compose-dev.yml up tracker_web (This will take some time and requires 
Internet access to pull and build all the containers)
5. At first start a default superuser with the username "test@test.com" and the password "admin" is created. This can 
be used to access the system, create contests and so on.

## Traccar setup (optional)
If full integration with traccar is required (optional). This is only required if any testing of the tracking 
functionality is to be done. Web interface with map generation will work without this.:
  1. Log into your local tracker instance, localhost:8082, by creating a new user.
  2. Click on the cog in the upper right-hand corner and select account.
  3. Click permissions and copy the token present in the "Token" field.
  4. Go to your mom, admin interface at localhost:8002/admin and click Traccar credentials.
  5. Enter the copied token into the "Token" field and click save
