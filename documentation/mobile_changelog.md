# Mobile app change log

Everything done for the new Air Sports Live Tracking mobile apps (Android and iOS), newest first, split into **Backend** (this
repository: API, push, admin, website) and **App** (the Kotlin Multiplatform app in `airsports-no/airsports-mobile`). Dates are
commit dates. The new apps replace the legacy `airsports_android` and `airsports_ios` apps and keep their store ids.

**Maintenance:** add an entry here, under today's date, for every mobile-related change in either repository (backend or app), in
the same commit or the next one. Keep each entry to one line that says what a pilot, an organiser or an admin gets.

---

## 2026-10-12

### Backend
- **Hangar flyer link.** The flyer's QR code now points to `https://app.airsports.no/get-app/?next=<registration page>` for both
  navigation sign-up and poker quick-register. The page offers Google Play or the App Store (Play carries the target through the
  install referrer) and "Continue in the browser". `/.well-known/assetlinks.json` (Play App Signing key and the developer debug key)
  and `/.well-known/apple-app-site-association` (team `3ZGT84Y36H`) let the apps open the link. Only paths on this site are accepted.
- **Organiser announcements.** `POST contests/<id>/announce/` (contest editors only) sends a message of up to 500 characters to the
  crews of a whole contest or one task as a push notification; `userprofile/announcements/` lists the ones from the last 24 hours that
  concern the pilot. New panel "Message the pilots" on the contest page, in the left column below the team list.
- **Score and flight orders for the pilot's app.** The current-flight endpoint carries `score` (the pilot's score so far) and
  `flight_order_path` (the newest generated flight order); the flight lists carry `flight_order_path`.
- **Task option `show_live_score_in_app`** (default on, in the task creation form and the Update task details modal): switches the
  running score and training mode in the app. A calculation delay holds both back.
- **Training feedback.** `training_feedback` (last timed gate and its offset in seconds, positive is late) and a
  `training_available` flag on the current-flight endpoint. Gates without a time check give no feedback; the server keeps the last
  timed gate separately (`last_timed_gate`, `last_timed_gate_time_offset` on the contestant track). No longer limited to self-managed tasks.
- **Push notifications:** "Tracking is still on" when the phone keeps sending positions 10 minutes or more after the flight window
  closed (not when another flight is open or within the hour); "Live scoring has finished: N points" after the calculation delay plus a
  settling time (only for people who may see the results).
- **Admin Statistics, new "Mobile apps" tab** (site admins only): who has the app connected (last request within 15 min / 1 h / 24 h /
  7 days), platform, version and build, count per version, and the phone's last position when the tracking stream has one. Fed by
  `X-App-Platform`, `X-App-Version` and `X-App-Build` headers (`MobileAppActivity`, written at most once a minute per user); the
  position processor now also caches each phone's latest coordinates (refreshed every 5 s, kept 6 h).
- **Website:** sign in and sign up with Google or Apple (Firebase auth domain `auth.airsports.no`, 60 s clock-skew tolerance); explanation of
  Apple's Hide My Email; the "Book start time" modal names the task; hangar flyer no longer prints the target URL; fixes to the
  contest dashboard and base template.
- **Infrastructure:** Helm rolling update no longer removes old pods before the load balancer has the new ones.
- **Migrations:** `0188` last timed gate, `0189` still-tracking push kind, `0190` announcements and flight-scored push kind, `0191`
  `show_live_score_in_app`, `0192` mobile app activity.

### App
- **Hangar flyer to registration.** Android app link and Play install referrer, iOS universal link; a link scanned before sign-in opens
  after it; the flyer link goes before the first-start tour.
- **Faster start.** Returning pilots see Home at once from the saved profile; profile, current flights, next flights and
  announcements are fetched at the same time; "Checking your flights…" instead of "No flight scheduled" until the first load is done.
- **First-start tour** (five skippable pages, replayable from the profile) and the **app version** on the login, home, profile and
  update-required screens.
- **Home and flight strip.** Announcement cards from the organisers (dismissible), running score in the strip, "Flight orders" and
  "Share live link" buttons, "Score so far" in the "Flight recorded" dialog. No "Flight registered" note when the flight is already shown.
- **Training mode** needs only the server's `training_available`; explanation text updated.
- **Warnings and safety.** Warning when tracking stays on after the flight window closed (in the dock), warning after 4 hours of
  tracking and automatic stop after 12 hours with a message (also a notification on Android); upload problems and "no position received"
  shown in the dock on the Timer and Photos pages too.
- **Timer.** Countdown buffer (whole minutes, default 0) moved to the Timer page with a "?" help; shorter text, scrolling content
  and a pinned START button so it fits small screens.
- **Pre-flight.** The location row asks for permission (Android) instead of only opening settings; an unknown connection is no
  longer shown as offline. Free access (staff or grant) from the saved profile unlocks tracking at once.
- **Persistent Back button on iOS** on every screen with somewhere to go back to.
- **Hidden debug view** (seven taps on the app version): GPS accuracy, the timing accuracy it gives at the current ground speed
  (± seconds, with a table for other speeds), fix age, clock offset, queue and upload status. GPS accuracy removed from the dock.
- **Versioning and release.** One version name in `version.properties` for both platforms; build numbers are separate per platform
  (iOS 200 + `ios-release` run number, Android `-PversionCode`). The unused email-link sign-in code was removed.
- **iOS Crashlytics** (release builds only, symbol upload in the release archive); privacy manifest lists crash data.
- **Platform headers** `X-App-Platform`, `X-App-Version`, `X-App-Build` on every authorised request (for the admin Mobile apps tab);
  the app posts nothing extra for it.

---

## 2026-10-11

### Backend
- **Photo observations.** Registration, scoring (photo ids, scorecard options, CIMA millimetre rules, tolerances configurable per
  scorecard) and live-map markers; navigation-task option "Allow observation registration in the app"; a 12 hour registration grace period;
  a crew endpoint that works for private tasks and carries no score; crew can cancel, register by time only (position from the
  reports) and correct to an earlier time; marks are final when tracking stops or the finished-by time passes, unmarked photos can still
  be marked from an offline queue; observation photos kept apart from waypoint photos; API document `documentation/photo_observations_api.md`.
- **Own flights for the app.** Listed also in private contests, slim payload with contest metadata and no route (much faster).
- **Open for registration today:** nearest venue first when the app sends the phone's position.
- **Current-flight endpoint:** `last_received_time` (not held back by the calculation delay) and `calculation_delay_minutes`.
- **Admin:** `send_test_push <email>` management command; read-only admin pages for registered phones and the push log.
- **Training feedback** first version (last gate and its time offset for self-managed tasks without a calculation delay).
- **Migrations:** `0186` photo observation, `0187` task option for observation registration.

### App
- **Redesign.** Barlow type, ink/paper/indigo theme (light and dark), flight strip on Home, typographic menu tiles, the bottom
  "flight deck" with a Flight / Timer / Photos switch (counter such as 2/5 on Photos), amber photo marking.
- **Training mode** (gate timing feedback, polled every 5 s), **pre-flight check** ("Ready to fly?", later "Pre-flight"), low-battery
  warning, screen on while tracking, richer stop confirmation (flight and duration).
- **Track history and GPX export.** Every tracking session is recorded on the phone (one fix per second); share a GPX 1.1 file with UTC
  times, delete one session or all finished ones.
- **Photo observations** in the app: thumbnail grid or list, mark with the current GPS fix, offline queue, cancel a mark, set the time
  by typing it, marks final when the flight is over, no scoring feedback to the crew.
- **Timer countdown buffer** (timer starts at -N:00). **Open for registration today** uses the phone's approximate position.
- **Private contests:** flights named and decorated from their own metadata; the map is marked private.
- **Home:** subscription and "keep tracking reliable" moved to Profile, training mode at the bottom with a "?", dashboard as a plain
  link at the bottom.
- **iOS.** Location permission and precise-location flow, privacy manifest, iPhone only, plain GNSS accuracy
  (`kCLLocationAccuracyBest`, no sensor-fusion smoothing), ad-hoc signed simulator build with a keychain access group (fixes the
  Appetize keychain error), simulator app kept as an artifact for Appetize.

---

## 2026-10-10

### Backend
- **Mobile foundation.** FCM device registration and push notifications (tracking window opens, flight started without positions,
  scoring started), public `mobile/config` endpoint with minimum supported versions, in-app account deletion API (migrations `0183`, `0184`).
- **Current-flight endpoint** gives the pilot's status: `calculator_running`, `map_viewable` and `map_path` per contestant; `can_cancel`
  on the pilot's own upcoming flights.
- **Open for registration today:** web page, public endpoint and a mission-dashboard tab with search, dates and time zone, private-task
  rules; embed mode for the apps' web views; registering a flight in the app returns to the app (`airsportsapp://registered`).
- **Login for the apps' web views:** `firebase_login` honours a safe same-host `?next=` redirect, logs in with a backend that keeps the
  session, and does not follow `?next=` after a failed token login.
- **Free app tracking:** `app_tracking` entitlement grant in the admin (and staff) reported on the pilot's own profile; the profile matches
  the user's email case-insensitively (migration `0185`).
- **Website, alongside:** pilot dashboard (my flights first, app hand-off panel, cancel confirmation, replay link), concepts guide and
  contextual help, organiser and task-creation guidance, type-ahead person pickers that never expose email addresses (several
  autocomplete endpoints removed), registration edits in place, documentation refresh.

### App
- **Foundation.** Kotlin Multiplatform project (Compose Multiplatform UI) with a shared API client, durable offline position queue,
  Traccar uploader at one position per second, and a shared app state machine. Android and iOS (SwiftUI host, XcodeGen project) share it.
- **Sign-in.** Email and password with email verification, Google (Android and iOS) and Sign in with Apple (iOS); in-app account
  deletion. The older email-link sign-in was dropped from the UI.
- **Tracking.** Foreground location service with wake lock (Android), CoreLocation source (iOS), GPS status, battery tips, permission
  help, whether the server receives positions and whether scoring is running, free-access and store subscription (Play Billing, StoreKit 2).
- **Home and flights.** Tracked flight card (banner, logo, task type, times, speed, wind, links), upcoming and past flights joined with
  contest and task names, cancel an upcoming flight (also while underway), view your flight after stopping, minimum-version screen,
  push notifications, website pages in a web view signed in by header.
- **Timer.** Adaptive-start timer on the nearest whole minute, GPS time on Android, phone clock checked against network time on iOS.
- **Release tooling.** Android launcher icon and signing config, TestFlight workflow (automatic signing with an App Store Connect key),
  iOS CI with macOS-minute savings, a manual simulator run with screenshots and logs.
