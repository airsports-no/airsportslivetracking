# Air Sports Live Tracking
Air Sports Live Tracking (ASLT) is an online (live) scoring platform for aircraft competitions. Currently it is primarily focused on precision flying and air navigation race (ANR), but it also supports other task types such as poker run and the novel Air Sports Challenge.

Our primary server is up and running at https://airsports.no/ for anyone to use free of charge. We are looking for funding to keep this service available.

ASLT can be run locally using the docker-compose.yml file, and it is designed to be deployed to GKE using helm.  There are two accompanying apps, [Airsports Google Play](https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1) and [Airsport Apple Appstore](https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&itscg=30200) that integrate with the user management system of ASLT. The repository includes a client also for Microsoft flight simulator 2020 (MFSFS2020).

# Documentation
A user manual for content creators is available [here](documentation/Airsports%20Live%20Tracking%20user%20manual.pdf). It is a bit outdated and contributions are welcome. An additional user manual for the results service can be downloaded [here](documentation/Using%20the%20Air%20Sports%20Live%20Tracking%20results%20service.docx).

## API
The API is documented using [swagger](https://airsports.no/docs/). This [guide](documentation/AirSports%20third%20party%20contest%20tool%20API.docx) provides a brief overview of how to use the api to create new navigation tasks and manage contestants.

## Tracking
ASLT uses the [traccar.org](traccar.org) open source tracking server for receiving position reports from users. This allows for support of a wide range of hardware and software trackers.

## Contributions
The project welcomes contributions of all kinds in the form of pull requests. Areas were contributions are specifically welcome include:
- User documentation
- Translation
- New task types

The project is currently in the early stages of open source release, so some work is required to clean up the code base to make it more easily maintainable. Check the [implementation guide](../../wiki/Implementation-guide) for some hints.

### Structure
Everything is built upon Django, React, and Python 3.12. Refer to [the wiki](../../wiki/Model-architecture) for a brief description of the most important models. Information about the scoring engine and how the live tracking works is found in [this wiki page](../../wiki/Scoring-engine)

### Building locally
The project comes with a docker-compose.yml file that can be used to build and test locally. Simply execute
```
docker compose build
```
to build all required images.

- tracker_daphne: Is the web server that services both http and websocket traffic.
- tracker_celery: Django batch processing.  Does track recalculation and flight order generation in the background.
- tracker_processor: Interfaces with traccar to receive incoming position reports and executes contestant processors either internally or as kubernetes jobs.

 Additional images that are part of the compose file are:
 - mysql (database)
 - redis (caching and interprocess communication)
 - traccar (local traccar.org server)

The helm chart used for production employment has a few additional dependencies:
- wordpress: Hosts home.airsports.no. This should eventually be moved through a separate stand-alone chart.
- mbtils: Basic tile server used to serve certain maps to the navigation map generation process.

These additional dependencies are not required for executing locally and are therefore not part of docker-compose.yml.

A full local development environment can be started by running:
```
docker compose up
```
This executes the three primary containers which also brings up the additional infrastructure containers. The Web server can be accessed at http://localhost:8002/.  A default superuser is created with username test@test.com and password admin. This can be used to login through the web interface.

## MSFS 2020 client
Source code is available at [asltmsfs](https://github.com/airsports-no/asltmsfs).  Binary distribution is available at [Airsports MSFS client](https://drive.google.com/drive/folders/1Nj54XMtQ3HOBNJs_PEudNyfFpeH6Aekk?usp=sharing) together with user documentation. It can be used to compete in Air Sports Live Tracking tasks using Microsoft Flight Simulator 2020. By modifying the traccar server address can also be used to test locally.
