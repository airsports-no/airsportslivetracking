# Mobile app change log

What has been built for the new Air Sports Live Tracking mobile apps (Android and iOS), split into **Backend** (this repository:
API, push, admin, website) and **App** (the Kotlin Multiplatform app in `airsports-no/airsports-mobile`). The new apps replace the
legacy `airsports_android` and `airsports_ios` apps and keep their store ids.

**How this file is kept:** the first part describes the initial development (10-12 October 2026) as one finished whole, without
the intermediate steps. Every later change is added under its own date heading at the top of "Changes after the initial development",
newest first, with a Backend and an App part. Add the entry in the same work item as the change, in either repository, as one line
that says what a pilot, an organiser or an admin gets.

---

## Changes after the initial development

### 2026-10-17
#### Backend
- **Deleting the account in the app no longer fails with a server error.** The removed Firebase login package left two tables in the database with a foreign key to the user, so deleting any user failed (Sentry `PYTHON-DJANGO-1Z`, 500 from `delete_account/`). Migration `0199` drops the two unused tables, which also fixes deletion from the admin.
- **The profile no longer carries `is_public` and `last_seen`.** Both fields on the person (profile and crew in the API) are gone: nothing read them (neither the apps nor the MSFS client), and `last_seen` cost a database write for every received position. The tracker list of a contestant no longer has `is_active`. Migration `0198`.
- **The task wizard asks "Who will fly this task?" first.** Real aircraft only, simulators allowed, or simulator only, as three plain choices at the top of the task details (also when editing a task), instead of a buried drop-down.
- **The results page's "Replay track" link works, and links to the contest.** Website only.
- **Task wizard sends `rounded_corners=false` when the checkbox was never touched** (16 October). Website only.

#### App
- **My flights looks like the rest of the app.** Upcoming and past flights are the same flight cards as on Home (contest logo, task type, tracking window, take-off, airspeed and wind), under day headings (Today, Tomorrow, Sat 24 Oct), with tabs, a spinner, a Refresh button and, when there is nothing to show, a button to find an event. Cancel, flight orders, directions and the map or results work as before.
- **"Register today" is a list in the app.** The events open for self-registration today are cards with the country, the distance from the phone (nearest first), an "Open now" label, directions and a **Register a flight** button that opens the website's form for that task. The phone's position stays on the phone and is only used to sort the list. If the list cannot be loaded, the website's list is offered. Android first; the iOS build was not run for this change.
- **Training mode on by default in the phone apps too** (as in the MSFS client). It is on at every app start, shows only where the organizer allows it for the navigation task, and the pilot can switch it off.
- **MSFS client: training mode on by default.** It is on at every start (and after sign-out), and still only shows where the organizer allows it; the pilot can switch it off.
- **MSFS client: photo marks update in place.** A new photo mark could stay hidden until the screen was reopened; each card is now updated in place.
- **MSFS client: build 43 on flightsim.to**, with crash reports mentioned in the README and listing.
- **Home asks the server again when the next window opens** (app PR #3). While the pilot is on Home and not tracking, the app waits until the next flight's window opens, then asks for the current flight (retrying every 10 s for up to 2 minutes), so the "not active yet" note goes and Timer and Photos appear without pressing Refresh. The card also uses a ticking time. While tracking, the existing poll already did this.
- **Home says plainly when the next flight is not active yet** (app PR #2; the MSFS client got the same in its PR #18). Before the tracking window opens the server has no current flight, so positions are not scored. The header now reads "Next flight, not active yet", the card starts with the tracking window (date and time, with the end date too if it runs past midnight) and an amber note says when it opens and that positions are not scored until then. The note is only shown for a window that opens later: an open window with no current flight (positions ignored, request failed) keeps the plain "Next flight".

### 2026-10-14
#### Backend
- **Sign in to the MSFS client with Google or Apple.** The client opens `accounts/desktop_sign_in/` in the browser, where
  the person signs in with the website's Google / Apple buttons. The browser is then sent back to the client on the same
  PC (`http://127.0.0.1:<port>/callback`) with a one-time code, which the client trades, together with a secret only it
  holds (as in OAuth PKCE), for a Firebase custom token (`accounts/desktop_sign_in/token/`): the same Firebase user as on
  the website and in the apps. Codes expire after two minutes and work once. Off when `SOCIAL_LOGIN_ENABLED` is off.

### 2026-10-13
#### Backend
- **The MSFS client counts in the app statistics.** Its requests (`X-App-Platform: msfs`) are now recorded like the phone apps',
  so the admin "Mobile apps" panel lists it as "MSFS client" with its version and build, and shows where the pilot's simulator
  aircraft is (the simulator tracking id) instead of their phone. It still cannot register for push notifications.
- **Flight notifications for the MSFS client.** It has no push, so the notifications the phones get (tracking opens soon, no
  positions, scoring started, tracking still on, flight scored) are also kept for a pilot who used the MSFS client in the last 30
  days, with wording for the client ("press play"), and `GET userprofile/client_notifications/?after=<id>` returns the new ones
  of the last 24 hours. "Tracking still on" now also looks at the simulator tracking id: the client is told about the simulator,
  the phone only about the phone. Still only while `PUSH_NOTIFICATIONS_ENABLED` is on. Admins see them under "Client
  notifications".
- **The MSFS practice flight is always flown at the quickstart's speed.** A pilot already signed up for the practice contest got
  their team's speed (e.g. 200 kt) on "Go flying"; the flight now gets the quickstart's speed (70 kt by default). Their team and
  its speed in the contest are not changed, and the website's own registration still uses the team's speed.

### 2026-10-16
#### Backend
- **Organizers can delete their own account in the app.** `DELETE userprofile/delete_account/` now accepts organizers (members of
  "ContestCreator", or anybody with the global add-contest permission); only staff and superusers are still refused (409, "Staff and
  administrator accounts must be deleted by support. Contact support@airsports.no."). The organizer's contests, routes, tasks, teams
  and every result are kept: the login, the profile (deleted, or anonymized when it is in a team, as before), the management rights and
  the uploaded maps go, and the contest no longer names a creator. Contests that nobody else can manage afterwards are listed in an
  e-mail to support (marked when running) so they can get a new manager. If a contest still runs on a token the organizer bought, the
  login row stays as an anonymous, deactivated tombstone (no name, address, password or rights) instead of being deleted. The deletion
  is one transaction together with the Firebase deletion: if the Firebase account cannot be deleted nothing is changed and the app gets
  503 with a message to try again. The 204 on success is unchanged.
- **The current-flight endpoints say when positions are ignored.** `get_current_app_navigation_task` and `get_current_sim_navigation_task` return a
  flight whose positions the task's simulator policy or the declared flight mode rejects (they used to hide it, so the pilot saw nothing),
  with `positions_accepted: false` and `positions_ignored_reason` in words for the pilot.
- **Terms and privacy page updated for 2.0** (`airsports_static/src/pages/terms_and_conditions.astro`, English and Norwegian), (merged to `main`, with the Crashlytics and MSFS-client Sentry wording): what the apps collect (precise location in the background while tracking, account data, push token, crash reports, app version activity), the SafeSky position feed (registration only), in-app account deletion, Google Cloud hosting in Finland, the third-party list (Firebase, Apple, Google, Sentry), version 2.0 of 16 October 2026.
- **The live map only shows observation photos for tasks that use observation registration.** The task `photos` endpoint now leaves the
  observation photos out for everyone but the organizers while "allow observation registration" is off; the route's waypoint photos stay.
- **Real flights and simulator flights are kept apart (`documentation/PLAN_simulator_separation.md`).** Every navigation task has a
  simulator policy: not allowed (the default, also for all existing tasks), allowed (simulator flights count like any other and carry
  a simulator badge) or simulator only. The position processor drops the positions the policy does not accept (a simulator tracking id
  on a task that does not allow simulators, a tracker or app on a simulator-only task) before any calculator starts, and notes the
  first time on the flight (`blocked_positions_at`, shown to organizers as "ignored"). The same filter decides the Traccar device ids
  used when a track is recalculated and which flight `get_current_sim/app_navigation_task` returns.
- **A flight now has a declared flight mode (real aircraft or simulator).** The website's "Book start time" has a required drop-down
  "How will you fly this?" (empty by default, with the consequence of a wrong choice spelled out; options the task does not accept are
  disabled). The MSFS client and the phone apps are recognised by the server and do not ask: from `X-App-Platform`, or from
  `?client=msfs|android|ios`, which their embedded web pages now send and `EmbedModeMiddleware` keeps in a cookie. A registration the task
  does not accept is refused with a clear message, a flight only uses positions of its own kind, and `open_registration_today` lists only
  the tasks that accept the asking client's flights. Registration without a flight mode now needs the website's choice (400 otherwise).
- **The MSFS practice flight only offers a task that accepts simulators.** `current_quickstart` skips a quickstart whose task is "not
  allowed", the admin refuses to save one, and the one-press registration declares a simulator flight.

#### App
- **"Your flight is not being recorded".** The phone apps and the MSFS client show a notice on Home with the server's reason when their
  positions are ignored for the current flight (for example a simulator pilot on a flight booked as a real one).
- **MSFS client crash reporting is built.** Release builds of the client send unhandled exceptions and startup sessions to Sentry: the DSN is built into the release (`SENTRY_DSN` repository variable or secret), the release is `msfsclient@<version>+<build>`, and the pilot's Airsports user id (never the name or e-mail) tags the report. `documentation/msfs_client_sentry.md` keeps the plan. It sends nothing until `SENTRY_DSN` is set in the client repository.
- **Training banner readable.** The gate label ("SP on time") was dark on the dark dock; it is now light. The preview run used for store screenshots got sample images, a running flight with score and training, and a synthetic GPS track. Store screenshots (iPhone, and cropped for Play) and the 2.0 store listing (English and Norwegian) are in `docs/store-screenshots/` and `distribution/store-listing/` of the app repository.
- **Web pages opened in the app say which client opens them** (`embed=app&client=android|ios`), so a flight booked there is a real
  flight and the open-today list only shows tasks that accept real flights. The MSFS client does the same with `client=msfs`.
- **Cancel on Home follows My flights.** Home now looks the flight up among all upcoming flights (it used to fetch only the first three), so the Cancel flight button shows exactly when the same flight can be cancelled on the upcoming flights page.
- **Home layout.** The link buttons on the next-flight card now wrap, so "Cancel flight" is no longer cut off on narrow phones (it still shows only when the server allows cancelling). The footer links are compact text links with the version line. The "Flight cancelled." note on the flights list disappears after four seconds and when the page is left or reopened.
- **First Android test build on Google Play.** Version 2.0.0 (201) was built by `android-release` and uploaded to the internal testing track.
- **Production path in the Android release workflow.** `android-release` can release to production: it needs `publish` typed in a confirmation
  field, runs from `main` only, rolls out in stages (10, 25 or 50 percent, or 100), runs in the GitHub environment `production` (required reviewers can be
  set there), sends release notes from `distribution/whatsnew/` and tags the commit `android-v<version>-<build>`.

### 2026-10-15
#### App
- **Android test builds can be uploaded to Google Play from CI.** The manual `android-release` workflow builds the signed release bundle with the
  new upload key (version name from `version.properties`, build number 200 plus the run number), checks that it is signed and uploads it, with the
  R8 mapping file, to a Play track (internal testing by default). It needs the keystore, the real `google-services.json` and a Play
  service-account key as repository secrets.

### 2026-10-14
#### App
- **"Restore purchases" now really restores.** The button used to re-read the subscription only; it now asks the store to sync first (iOS
  `AppStore.sync()`, which may ask for the Apple ID password) and then says what it found ("Your subscription was found" or why not). On iOS
  the message notes that App Store purchases are not visible in TestFlight builds, which use a test store.

### 2026-10-12
#### Backend
- **MSFS quickstart: a practice flight for new simulator pilots.** Admins set up a `SimulatorQuickstart` (Django admin): a
  self-managed navigation task, where to start in the simulator as text (e.g. "Kjeller (ENKJ), runway 30") and an altitude for an
  in-air start. `GET userprofile/msfs_quickstart/` gives the MSFS client the newest active one (404 when none): task, start text,
  a ground start (take-off gate, runway heading) and an air start (2 NM before the starting point on course) computed from the
  route, the registration page and the pilot's own registration.
- **MSFS quickstart: one-press registration.** `POST userprofile/msfs_quickstart_register/` signs the pilot up for the practice
  contest with the quickstart's aircraft, club and speed (defaults "MSFS", "MSFS pilots", 70 kt; a pilot already signed up keeps
  their own team) and sets up the flight with no wind and an adaptive start whose window is open now (two hours to cross the
  starting line). Registering again returns the same flight. The flight order is made in the background and e-mailed as on the
  website; `registered_flight.flight_order_path` in `msfs_quickstart` is set once it is ready, so the client can poll for it. The
  website's self-registration now shares the code that creates the flight (`services/self_registration.py`).
- **MSFS quickstart follows the website's visibility rule.** A practice flight in a non-public task or contest is only offered
  (`msfs_quickstart`, otherwise 404) and registered for (`msfs_quickstart_register`, otherwise 400) when the signed-in user may view
  the contest; a public task in a public contest is offered to everybody, as before. A new pilot who has no profile yet can press
  register straight away, and a double press makes one flight.
- **Photo observations close five minutes after the tracking window, and until then everything can be changed.** The registration
  grace period was 12 hours; it is now five minutes at most (`OBSERVATION_REGISTRATION_GRACE_MINUTES` can only shorten it). Until then
  the crew can mark, change (replace) and cancel observations; after that nothing can be registered, changed or cancelled (409). The
  earlier "marks are final when the flight is over" rule is removed (`may_change_marks` and the `locked` answer are gone).
  `observation_photos` carries `registration_closes_at` and `registration_grace_minutes`; the task option's help text and
  `documentation/photo_observations_api.md` state the rule. The observation time must still lie within the flight.

#### App
- **Photos page states the marking deadline** ("you can mark, change or cancel photos until 5 minutes after your tracking window
  closes (12:05:00). After that nothing can be marked or changed") and says "Marking has closed" once it has passed. The "(final)" marks
  and the "marks are final" note are gone.
- **Cancel flight on Home.** The next-flight and tracking cards get a "Cancel flight" button whenever the flight can be cancelled from
  My flights (same server rule and confirmation, also for a flight underway).

_Add new dates above this line, newest first, each with a Backend and an App part._

---

## Initial development (10-12 October 2026)

### Backend

**Mobile API**
- Device registration for push notifications (FCM), a public `mobile/config` endpoint with the minimum supported app version per
  platform, and self-service account deletion.
- The pilot's current flights (`get_current_app_navigation_task`) carry what the app shows while tracking: whether the live
  calculator runs, when the server last received a position (not held back by the calculation delay), the task's calculation
  delay, whether the pilot may open the live map and its path, whether observation registration is on, the pilot's score so far,
  the newest flight order, and the training-mode fields below.
- The pilot's own flights (upcoming and past) are listed also in private contests, with a slim payload (schedule, contest and task
  names, images, venue, no route), which is much faster. Upcoming flights say whether the pilot may cancel them and offer the newest
  generated flight order.
- Free app tracking: an `app_tracking` entitlement grant (Django admin, with expiry and notes) and staff accounts are reported on
  the pilot's own profile, so the app needs no store subscription for them. It is separate from task and contestant budgets.

**Registration and web views**
- "Open for registration today": a web page and public endpoint (also a tab on the mission dashboard) with search, dates in the
  venue's time zone, private-task rules, and the nearest venue first when the app sends the phone's position.
- Embed mode for the apps' web views, and registering a flight in the app returns the pilot to the app
  (`airsportsapp://registered`) instead of the live map.
- `firebase_login` (the app signs web views in through a header) honours a safe same-host `?next=` redirect, logs in with a backend
  that keeps the session, and does not follow `?next=` after a failed token login.

**Photo observations**
- Crews register observation photos from the app while a flight is tracked: registration, scoring (photo ids, scorecard options,
  CIMA millimetre rules, tolerances configurable per scorecard), a 12 hour registration grace period and live-map markers
  (following the task's "Display secrets" setting).
- A crew endpoint that works for private tasks and carries no score; crews can cancel a mark, register by time only (the position is
  taken from the position reports) and correct to an earlier time. Marks are final when tracking stops or the finished-by time
  passes; unmarked photos can still be marked from an offline queue.
- Task option "Allow observation registration in the app"; observation photos are kept apart from waypoint photos. API description:
  `documentation/photo_observations_api.md`.

**Live feedback in the app**
- Task option `show_live_score_in_app` (default on; task creation form and Update task details): pilots get a running score and
  training mode. A calculation delay holds both back. The score appears only where the pilot may see the results.
- Training mode: `training_available` and `training_feedback` give the last gate with a time check and how far from its required
  time it was passed (seconds, positive is late). The server keeps the last timed gate separately on the contestant track; gates
  without a time check give no feedback.

**Notifications and messages**
- Push notifications: tracking window opens soon; flight started but no positions received; scoring has started; tracking is still
  on 10 minutes or more after the window closed (not when another flight is open or within the hour); live scoring has finished with
  the points (after the calculation delay plus a settling time, only for people who may see the results). Each is sent once per
  flight and only when push is enabled.
- Organiser announcements: `POST contests/<id>/announce/` (contest editors only) sends up to 500 characters to the crews of a contest
  or one task, as a push and as a notice in the app for 24 hours (`userprofile/announcements/`). The contest page has a "Message the
  pilots" panel in the left column below the team list.

**Hangar flyer and app links**
- The flyer's QR code points to `https://app.airsports.no/get-app/?next=<registration page>` for navigation sign-up and poker
  quick-register. The page offers Google Play (carrying the target through the install referrer) or the App Store, and "Continue in
  the browser". `/.well-known/assetlinks.json` (Play App Signing key and the developer debug key) and
  `/.well-known/apple-app-site-association` (team `3ZGT84Y36H`) let the apps open the link. Only paths on this site are accepted.

**Admin**
- Statistics, new "Mobile apps" tab (site admins only): which apps are connected (last request within 15 min, 1 h, 24 h or 7 days),
  platform, version and build, a count per version, and the phone's last position when the tracking stream has one. It is fed by
  `X-App-Platform`, `X-App-Version` and `X-App-Build` headers (written at most once a minute per user); the position processor also
  caches each phone's latest coordinates (refreshed every 5 seconds, kept 6 hours).
- `send_test_push <email>` management command and read-only admin pages for registered phones and the push log.

**Website changes made alongside**
- Sign in and sign up with Google or Apple on the website (Firebase auth domain `auth.airsports.no`, 60 seconds of clock-skew
  tolerance, an explanation of Apple's Hide My Email).
- Pilot dashboard (my flights first, app hand-off panel, cancel confirmation, replay link), concepts guide with contextual help,
  organiser and task-creation guidance, type-ahead person pickers that never expose email addresses, registration edits in place,
  a documentation refresh.
- Helm: a rolling update no longer removes the old pods before the load balancer has the new ones.

**Database migrations:** `0183` mobile devices and push log, `0184` scoring-started push, `0185` free app tracking grant, `0186`
photo observation, `0187` observation registration option, `0188` last timed gate, `0189` still-tracking push, `0190` announcements and
flight-scored push, `0191` `show_live_score_in_app`, `0192` mobile app activity.

### App

**Architecture and release**
- One Kotlin Multiplatform project with a Compose Multiplatform UI shared by Android and iOS (SwiftUI host, XcodeGen project): shared
  API client, durable offline position queue (SQLDelight), Traccar uploader at one position per second, and one app state machine.
- One version name for both platforms in `version.properties`; build numbers are separate per platform (iOS 200 plus the
  `ios-release` run number, Android `-PversionCode`). The version is shown on the login, home, profile and update-required screens.
- CI: Android build, tests and lint; iOS build and tests on the macOS runner (only when shared or iOS files change); a manual
  simulator run with sample data, screenshots and logs, and the `.app` as an artifact (for Appetize); a manual TestFlight workflow
  with automatic signing; the simulator build is ad-hoc signed with a keychain access group so Firebase sign-in works.
- Crash reports: Crashlytics on Android and on iOS (release builds only, with symbol upload); the iOS privacy manifest lists crash
  data. A hidden debug view (seven taps on the app version) shows GPS accuracy and what it means for gate timing at the current
  speed.

**Sign-in and account**
- Email and password with email verification, Google, and Sign in with Apple on iPhone; password reset; profile editing with photo;
  in-app account deletion; a first-start tour (five skippable pages, replayable from the profile).
- Subscription: tracking needs a store subscription (Play Billing, StoreKit 2; a simulated store in debug builds) or the free-access
  flag. Subscription and "keep tracking reliable" live under the profile. Free access from the saved profile applies at once.
- Server-driven minimum version (blocking "update required" screen).

**Tracking and reliability**
- Foreground location service with wake lock (Android) and CoreLocation (iOS, plain GNSS accuracy without sensor-fusion smoothing);
  precise-location and permission help; GPS status; battery tips; the screen stays on while tracking.
- Pre-flight check: flight scheduled, subscription, precise location, battery saver, battery level, internet, clock and GPS, each
  problem with a button that fixes it.
- Dock warnings: low battery, GPS lost, upload problems and "no position received" (also on the Timer and Photos pages), a warning
  after 4 hours of tracking and when tracking stays on after the flight window closed; tracking stops by itself after 12 hours with a
  message (and a notification on Android). Stopping asks for confirmation and names the flight and how long it has run.
- Faster start: returning pilots see Home at once from the saved profile; profile, flights and announcements load in parallel.
- Track history: every session is recorded on the phone (one fix per second); share a GPX 1.1 file with UTC times, delete one
  session or all finished ones.

**Home, flights and the flight deck**
- Redesign: Barlow type, ink/paper/indigo theme in light and dark, a flight strip for the next or active flight (contest and task,
  window, take-off, airspeed, wind, contestant, score so far), typographic menu tiles, and a bottom "flight deck" with tracking
  state, play/stop and a Flight / Timer / Photos switch.
- My flights (upcoming and past, cancel with the server's verdict, also while underway), the live map and results in a web view signed
  in by header, "Open for registration today" with the phone's position, view your flight after stopping, private contests named from
  their own metadata, a link to the website dashboard, terms and privacy.
- After the flight: your score so far, a notice when live scoring has finished, flight orders (opened in the browser) and a share
  button for the live link. Organiser announcements show as dismissible cards on Home.
- Training mode (on by default, the pilot can switch it off; it shows after each timed gate how early or late it was; only where the server offers it).

**Timer and photos**
- Adaptive-start timer on the nearest whole minute (GPS time on Android, phone clock checked against network time on iOS), an
  optional countdown buffer on the timer page, a pinned START button that fits small screens.
- Photo observations: thumbnail grid or list, mark with the current GPS fix, an offline queue, cancel a mark, set the time by typing
  it, marks final when the flight is over, no scoring feedback to the crew.

**Links and notifications**
- Push notifications (FCM; over APNs on iOS) with foreground banners; the hangar flyer's link opens the app (Android app link and Play
  install referrer, iOS universal link) and continues the registration after sign-in; the app sends its platform, version and build
  as headers for the admin Mobile apps tab and posts nothing extra for it.

**iOS specifics**
- iPhone only, a persistent Back button on every screen with somewhere to go back to, Sign in with Apple, photo picker, location
  permission flow, StoreKit 2 with the existing product ids, associated domain for the flyer link.
