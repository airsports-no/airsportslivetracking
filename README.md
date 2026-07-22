# Air Sports Live Tracking
Air Sports Live Tracking (ASLT) is an online (live) scoring platform for aircraft competitions. Currently it is primarily focused on precision flying and air navigation race (ANR), but it also supports other task types such as poker run and the novel Air Sports Challenge.

Please join our [Slack community](https://join.slack.com/t/airsportslivetracking/shared_invite/zt-2mmaui668-tEaJvJgoqg7782m3bdTleg)

Our primary server is up and running at https://airsports.no/ for anyone to use free of charge. We are looking for funding to keep this service available.

ASLT can be run locally using the docker-compose.yml file, and it is designed to be deployed to GKE using helm.  There are three accompanying apps, [Airsports Google Play](https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1), [Airsport Apple Appstore](https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&itscg=30200) and [Airsports for MSFS](https://apps.microsoft.com/detail/9N4MZBKPDS5X?hl=en-us&gl=NO&ocid=pdpshare) that integrate with the user management system of ASLT. This has been successfully tested for both MSFS 2020 and MSFS 2024.

# Documentation
A user manual for content creators is available [here](documentation/Airsports%20Live%20Tracking%20user%20manual.pdf). It is a bit outdated and contributions are welcome. An additional user manual for the results service can be downloaded [here](documentation/Using%20the%20Air%20Sports%20Live%20Tracking%20results%20service.docx). Both these documents should preferably be moved to the wiki for easy maintenance and improved availability.

## API
The API is documented using [swagger](https://airsports.no/api/schema/swagger-ui/). This [guide](documentation/AirSports%20third%20party%20contest%20tool%20API.docx) provides a brief overview of how to use the api to create new navigation tasks and manage contestants.

## Tracking
ASLT uses the [traccar.org](traccar.org) open source tracking server for receiving position reports from users. This allows for support of a wide range of hardware and software trackers.

## Contributions
The project welcomes contributions of all kinds in the form of pull requests. Areas were contributions are specifically welcome include:
- User documentation
- Translation
- New task types
- User interface improvements

The project is currently in the early stages of open source release, so some work is required to clean up the code base to make it more easily maintainable. Check the [implementation guide](../../wiki/Implementation-guide) for some hints.

### Structure
Everything is built upon Django, React, and Python 3.12. Refer to [the wiki](../../wiki/Model-architecture) for a brief description of the most important models. Information about the scoring engine and how the live tracking works is found in [this wiki page](../../wiki/Scoring-engine)

## Development quick start
To quickly get started with development simply check out the repos story and build the dev container, preferably in vscode. This sets up the full development environment, starts watching builders for the front end resources, starts the development web server, the celery instance, and the position processor.  These are controlled by tasks.json.

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

The helm chart used for production employment has an additional dependency:
- mbtils: Basic tile server used to serve certain maps to the navigation map generation process.

These additional dependencies are not required for executing locally and are therefore not part of docker-compose.yml.

A full local development environment can be started by running:
```
docker compose up tracker_daphne
```
This executes the three primary containers which also brings up the additional infrastructure containers. The Web server can be accessed at http://localhost:8002/.  A default superuser is created with username test@test.com and password admin. This can be used to login through the web interface.

#### Running frontend compilers

After optimizing the docker image the various front end systems must be compiled outside of the container. For development the docker compose file maps they build results into the container. This is done in the following manners:


##### Vite react

```bash
cd react_vite/
npm ci
npm run build
```

##### Tailwind

```bash
npm ci
src/static/css/tailwindcss -i src/static/css/input.css -o src/static/css/output.css --watch
```

## MSFS 2020 client
Source code is available at [asltmsfs](https://github.com/airsports-no/asltmsfs).  Binary distribution is available at [Airsports MSFS client](https://drive.google.com/drive/folders/1Nj54XMtQ3HOBNJs_PEudNyfFpeH6Aekk?usp=sharing) together with user documentation. It can be used to compete in Air Sports Live Tracking tasks using Microsoft Flight Simulator 2020. By modifying the traccar server address can also be used to test locally.

## Access control and free-tier configuration

ASLT now supports multiple access paths for contest capacity:
- free tier
- annual club pass
- single-event access grant
- manual override
- token-backed contest access

The free tier is configured through Django settings / environment, not through admin.

Relevant settings:
- `ACCESS_ENFORCEMENT_MODE`
  - `warn`: include capacity information in the UI/API but do not block actions
  - `enforce`: block task creation / registration once limits are reached
- `DEFAULT_FREE_CONTESTANT_LIMIT`
  - default contestant cap for contests that do not have a club pass, access grant, or token

Semantics:
- if a contest has no paid/override access path, these free-tier defaults are used
- if a value is unset / null / unlimited-equivalent, the corresponding limit is treated as uncapped
- contest creation and task/contestant registration consult the resolved access tier before allowing the action when enforcement mode is `enforce`

Operational recommendation:
- use `warn` while tuning limits or onboarding clubs
- switch to `enforce` once the desired pricing/capacity model is stable

Admin models involved:
- `AccessGrant`: annual pass, single-event pass, manual override, explicit grant records
- `ClubManagerMembership`: who may create/manage contests on behalf of a club
- `TokenType`: defines contestant/task capacity for a token package
- `UserTokenGrant`: grants token inventory to a user
- `ContestTokenAssignment`: binds a consumed token grant to a contest

ASLT is optimized for Google Cloud CDN. The caching strategy relies on three levels of invalidation:

1.  **Application Version (Global):**
    Defined by `SPECTACULAR_SETTINGS["VERSION"]` in `settings.py`. Bumping this version (e.g., `1.0.0` -> `1.0.1`) invalidates **every** list and detail view globally. Use this for deployments that change data structures.

2.  **Data Version (Dashboard/Lists):**
    Managed via `contest_list_version` in Redis. This version increments automatically via Django signals whenever a `Contest`, `NavigationTask`, or `Contestant` is modified. It surgically invalidates the ETags for all dashboard related requests.

3.  **Track Version (Telemetry):**
    Stored on the `Contestant` model in the database. The telemetry `/slice/` API uses an ETag derived from `track_version`. If a GPX is uploaded or a track is refreshed, only that specific contestant's telemetry cache is invalidated across the CDN.

**Cache Headers:**
-   **Public Data:** Uses `stale-while-revalidate`, allowing the CDN to serve data instantly while fetching updates in the background.
-   **Private Data:** Always marked `private, no-cache` to prevent sensitive data leakage to the CDN edge.
