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
#### App
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
- Training mode (the pilot switches it on; it shows after each timed gate how early or late it was; only where the server offers it).

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
