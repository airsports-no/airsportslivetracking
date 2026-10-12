# Plan: bring the Air Sports mobile app's features to the MSFS client (WinUI 3, C#)

For a coding agent working in the **Windows** environment on the `airsports-no/msfsclient` repository (WinUI 3, .NET 8, MVVM with
CommunityToolkit.Mvvm). The goal is to give the MSFS client the same features and the same look as the new Air Sports mobile app, as a
**C# port** (the Kotlin code cannot be reused). Where the simulator makes something meaningless (GPS, battery, permissions, push, store
subscriptions) it is replaced, as described in section 7.

Read this file first, then the reference implementation it points to. Nothing here has been built or run on Windows yet.

---

## 1. Where to find everything

| What | Where |
|---|---|
| The MSFS client (this port) | `https://github.com/airsports-no/msfsclient` (private; solution `msfsclient.slnx`, project `msfsclient/`) |
| The mobile app (**reference implementation**) | `https://github.com/airsports-no/airsports-mobile` (private). Kotlin Multiplatform; shared code in `shared/src/commonMain/kotlin/no/airsports/mobile/` |
| The backend (API, rules, tests) | `https://github.com/airsports-no/airsportslivetracking` (private). API in `src/display/viewsets.py`, services in `src/display/services/` |
| What was built and when | backend repo: `documentation/mobile_changelog.md` (read the "Initial development" section) |
| Photo observation API and rules | backend repo: `documentation/photo_observations_api.md` |
| Existing client notes | `GEMINI.md` in the msfsclient repo (architecture, SimConnect lifecycle, thread rules) |

**Method for every feature:** read the Kotlin implementation and its tests in the mobile repo, port the logic to C# in a plain class
library, port the tests, then build the WinUI screen on top. The Kotlin tests are the specification: port them case by case.

Kotlin reference files (mobile repo, under `shared/src/commonMain/kotlin/no/airsports/mobile/`):

| Area | Kotlin files |
|---|---|
| API client and JSON models | `api/AirsportsApi.kt`, `api/Models.kt` |
| App state machine (all flows) | `app/AppController.kt`, `app/AppSettings.kt`, `app/AppLink.kt`, `app/DeviceInfo.kt`, `app/AdaptiveStartTimer.kt` |
| Tracking, queue, upload | `tracking/*.kt` (`TrackingSession`, `PositionQueue`, `TraccarUploader`, `OsmAnd`, `ReceivingStatus`, `GpsStatus`, `WindowClosed`, `TrackingTargets`, `ClockCheck`) |
| Training and scoring feedback | `training/GateFeedback.kt` |
| Pre-flight | `preflight/Preflight.kt` |
| Track history and GPX | `history/TrackLog.kt`, `history/Gpx.kt` |
| Photo observations | `observations/*.kt`, `ui/ObservationsScreen.kt` |
| Screens | `ui/*.kt`, `ui/components/Components.kt`, `ui/theme/Theme.kt` |
| Fonts and logo | `shared/src/commonMain/composeResources/font/*.ttf`, `drawable/airsports_logo_white.png` |
| Tests (the specification) | `shared/src/commonTest/kotlin/...` and `shared/src/androidUnitTest/kotlin/...` |

---

## 2. Architecture for the port

Split the solution so most of the logic builds and tests without WinUI:

```
msfsclient.slnx
  msfsclient.Core/          net8.0 class library: API client, models, view-model logic, tracking, queue, GPX, rules  (no UI types)
  msfsclient.Core.Tests/    xUnit tests, ported from the Kotlin tests
  msfsclient/               the existing WinUI 3 app: XAML views, view models, SimConnect service, Windows specifics
```

- **Core** has no reference to WinUI or SimConnect. Define interfaces for what only Windows can do (`IPositionSource`, `IClock`,
  `ISecureStore`, `IShareService`, `INotificationService`) and implement them in the WinUI project. This mirrors the Kotlin design.
- Keep the existing services where they work (`IAuthService`, `IProfileService`, `ITraccarService`, `ISimConnectService`) and fold them into
  Core behind the same interfaces where possible. Replace `ProfileService`/`TraccarService` internals when the new API client supersedes them.
- Use `System.Text.Json` with a `SnakeCaseLower` naming policy (the API is snake_case) and `JsonIgnoreCondition`/defaults that tolerate
  missing and unknown fields. Every model field in `api/Models.kt` has a default so older servers keep working; do the same.
- Persistence: SQLite (`Microsoft.Data.Sqlite`) for the position queue, the track log, the observation queue and settings, same tables
  as the Kotlin schema (`shared/src/commonMain/sqldelight/no/airsports/mobile/db/*.sq`).
- Threading: all UI updates through `DispatcherQueue` (see `GEMINI.md`). Core code is async and UI-agnostic.
- State: one `AppController`-like class in Core (`AppState` as an immutable record, changes published as an event or `IObservable`), with
  the WinUI view models as thin wrappers. Port `AppController.kt` method by method; names can stay.
- Build and test locally on Windows with `dotnet build` and `dotnet test`. Core and Core.Tests must also build on Linux (`ubuntu-latest` or
  WSL) so CI can run the tests cheaply; only the WinUI project needs Windows.

---

## 3. Backend contract

Base URL `https://airsports.no/api/v1/`. Auth: `Authorization: JWT <Firebase ID token>`; on 401/403 refresh the token once and retry
once (`AirsportsApi.authorizedRaw`). The Firebase project is `airsports-613ce` (the client already signs in with Firebase REST).
The account must have a verified email.

Endpoints (all under the base URL; see `AirsportsApi.kt` for bodies and models):

| Purpose | Endpoint |
|---|---|
| Profile (get, patch, picture) | `GET userprofile/retrieve_profile/`, `PATCH userprofile/partial_update_profile/` (multipart for the picture) |
| Delete account | `DELETE userprofile/delete_account/` with `{"email": ...}` |
| Minimum version etc. | `GET mobile/config/` (public) |
| **Current flights for the simulator** | `GET userprofile/get_current_sim_navigation_task/` (404 = nothing scheduled). **The mobile app uses `..._app_...`; the simulator client must use the `sim` variant**, which returns the same payload for the pilot's *simulator* tracking id |
| Upcoming and past flights | `GET userprofile/my_future_flights/`, `GET userprofile/my_previous_flights/` |
| Contests by id | `GET contests/?pks=...` (cursor pagination) |
| Cancel a flight | `DELETE contests/{contest}/navigationtasks/{task}/delete_self_managed_contestant/{contestant}/` |
| Photo observations | `GET contestant/{id}/observation_photos/`, `POST contestant/{id}/photo_observations/`, `DELETE contestant/{id}/photo_observations/{obs}/` |
| Announcements | `GET userprofile/announcements/` |
| Web pages in the app | `https://app.airsports.no/firebase_login/?next=<path>` with the token in the `Authorization` header, never in the URL (use WebView2 and set the header on the first request) |

Tracking upload (unchanged from the current client): Traccar OsmAnd protocol to the Traccar base URL, device id = the profile's
**`simulator_tracking_id`**, `timestamp` in **seconds**, `speed` in **knots**, `lat`/`lon` with a dot decimal separator (use
`CultureInfo.InvariantCulture`). See `tracking/OsmAnd.kt`. Do not send the Firebase token to Traccar (separate `HttpClient`).

Headers on every authorised request (so the admin "Mobile apps" statistics can list the client): `X-App-Platform`, `X-App-Version`
(e.g. `2.0.0`), `X-App-Build`. The server currently accepts only `android` and `ios`; the **backend change in section 9** adds `msfs`.

---

## 4. Features to port (with the rules that matter)

Port in this order (it is also the milestone order in section 8). For each, the Kotlin file and its tests are the specification.

### 4.1 Sign-in and account
- Email and password with email verification gate, create account, password reset, sign out, delete account (confirmation, then
  `delete_account`). Keep the existing Firebase REST service. Google and Apple sign-in are optional (open the system browser flow later).
- First-start profile completion (name, country, phone) when the profile is not `validated`.
- Cached profile: store the last loaded profile and show Home at once at the next start, then refresh (`AppController.init`/`refresh`).
  Fetch profile, current flights, next flights and announcements **in parallel** at start.

### 4.2 Tracking from the simulator
- Source: SimConnect, one position per second (keep the existing 100 ms message pump and per-second data request). Each fix: UTC time,
  latitude, longitude, ground speed (knots), altitude, heading.
- Persist every fix first, upload in the background in batches of up to 200 with backoff 5 s doubling to 5 min, keep the queue up to
  200 000 fixes (`TrackingSession`, `PositionQueue`, `TraccarUploader`). Nothing is lost while offline.
- Record every session to the track log (section 4.8).
- Warnings and limits (`TrackingSession`, `WindowClosed`, `FlightDeck`): warn after **4 hours** of tracking, stop automatically after **12 hours**
  with a message; warn when tracking is still on **10 minutes** after the flight window closed (not when another flight is open or opens within
  an hour; the Kotlin test `WindowClosedTest` has the cases).
- Replace "GPS status" with **simulator status**: not connected, connected but no position yet, receiving (fix age).

### 4.3 Home, flight strip and flight deck
- Home shows: greeting, announcement cards (4.9), the flight strip for the flights open now (or the next flight), four tiles (Pre-flight, My
  flights, Track history, Register today), the training switch with its "?" help (only when the server offers it), links to the website
  dashboard and the terms (`https://airsports.no/terms_and_conditions/`), and the app version line.
- Flight strip (`HomeScreen.kt`, `tracking/TrackingTargets.kt`): contest and task, type, boxed facts (tracking window, take-off or
  "Adaptive", airspeed, wind, contestant number, **score so far** when the server sends one), links (Live map, Flight orders, Directions,
  Website), **Share live link**, **Cancel flight** (when the flight can be cancelled, with the confirmation dialog from `CancelFlightDialog`),
  private-map note. A green tab when the window is open, indigo otherwise.
- Bottom dock "flight deck" (`FlightDeck.kt`): play/stop, tracking state lines (receiving status from the server, scoring status, queued positions,
  battery line is dropped), a Flight / Timer / Photos switch (Timer only for adaptive-start tasks, Photos only where the task has observation
  registration, with a "marked/total" counter), the training banner, and the long-tracking and window-closed warnings.
- Polling while tracking: current flights every **10 s**, every **5 s** with training mode on (`App.kt`). The receiving status needs
  `last_received_time`; the "stale" limit is 45 s (`ReceivingStatus.kt`).
- Stop asks for confirmation and names the flight and how long tracking has run.

### 4.4 Timer (adaptive start)
`AdaptiveStartTimer.kt` and its test: the start minute is the nearest whole minute (30 s rounds up) of the moment Start is pressed, plus a
**countdown buffer** in whole minutes (0 to 30, default 0, stored in settings, set on the timer page with a "?" help). Display `m:ss` counting
down (rounding up) to the start minute, then up; the page scrolls and START is pinned at the bottom. The clock shown is the PC clock checked
against network time (`NtpClient`/`ClockCheck`: warn at 2 seconds or more, taking the measurement error into account).

### 4.5 Pre-flight check
`preflight/Preflight.kt` is pure logic. Rows for the simulator client: flight scheduled; internet; PC clock against network time;
simulator connected and receiving a position; subscription row is **omitted** (the simulator client needs none). Each problem has a text and,
where possible, a fix action. Summary line: "All clear", "N to look at" or "N to fix".

### 4.6 Training mode and live score
- Server fields on each active contestant: `training_available`, `training_feedback {last_gate, last_gate_time_offset}`, `score`.
- The pilot switches training mode on (off at every start). While on, show after each timed gate "<gate> <N s early|late|on time>" (within 2 s is on
  time; early is negative) in the dock (`training/GateFeedback.kt`); poll every 5 s. Show the **score so far** in the strip when `score` is set.
- The server decides availability (task option `show_live_score_in_app`, no calculation delay). Do nothing extra client-side.

### 4.7 Photo observations
`observations/*.kt`, `ui/ObservationsScreen.kt` and `documentation/photo_observations_api.md` (backend repo) are the specification.
- Photos page: thumbnail grid or list, **Mark** (stamps the *simulator's current position and UTC time*), Mark again, Cancel, Set time (typed time, no
  position: the server takes it from the position reports), offline queue sent in order.
- **Rule (write it on the page):** the crew can mark, change or cancel photos until **N minutes after the tracking window closes** (the
  server sends `registration_closes_at` and `registration_grace_minutes`, 5 at most); after that nothing can be marked or changed. Show
  "Marking has closed" once it has passed. There is no "final" state before that.
- A mark needs a fresh position (younger than 10 s) and a running tracking session.

### 4.8 Track history and GPX
`history/TrackLog.kt`, `history/Gpx.kt`, `GpxTest`, `TrackLogTest`. Record every session (start, end, every fix); list newest first with
duration and number of positions; **Export GPX** (GPX 1.1, `<time>` as UTC with a `Z`, coordinates as fixed decimals in the invariant culture,
file name `airsports-YYYY-MM-DD-HHMMZ.gpx`) through the Windows save/share dialog; delete one or all finished sessions (never the one being
recorded). A session left open by a crash ends at its last fix at the next start.

### 4.9 Messages, flight orders, flights
- Announcements (`GET userprofile/announcements/`): dismissible amber-edged cards on Home, dismissed ids kept locally; refresh at start and when
  the window gets focus. Desktop has no push: optionally show a Windows toast for a new announcement while the app runs.
- Flight orders: the strip button opens `https://app.airsports.no<flight_order_path>` in the browser.
- My flights (upcoming and past), cancel with the same confirmation dialog, "Register today" and the live map/results as WebView2 pages
  signed in by header (`WebScreen`): add `embed=app` to the path, intercept `airsportsapp://registered?...` navigations (return to Home and refresh).
- Home shows no "Flight registered" note when the registered flight is already the one the strip shows.

### 4.10 Shell, tour, debug, version
- First-start tour: five skippable pages (`TourScreen.kt`), shown once after the first Home load, replayable from the profile.
- Persistent **Back** button on every screen that has somewhere to go back to (a WinUI navigation back button in the title bar is fine).
- App version: "Airsports 2.0.0 (build)" on login, home, profile and the update-required screen, from `version.properties` semantics
  (one version name across platforms; the MSFS client keeps its own build number).
- Hidden debug view (seven taps on the version): replace GPS accuracy with simulator connection state, position rate, fix age, queue size, last upload error and clock offset.
- Minimum-version gate from `mobile/config` (blocking "update required" screen with the Store link).
- Crash reporting: pick one (Sentry is a good fit for .NET) and enable it for release builds only.

---

## 5. Design system

Port `ui/theme/Theme.kt` and `ui/components/Components.kt`; define the tokens as WinUI `ResourceDictionary` entries for light and dark theme.

| Token | Light | Dark |
|---|---|---|
| Ink (header, dock) | `#0E1726` | `#070D18` |
| Paper (background) | `#F3F5F9` | `#0A1220` |
| Card | `#FFFFFF` | `#121B2C` |
| Indigo (primary) | `#4338CA` | `#8B85F5` |
| Live green | `#12B76A` (text `#027A48`) | `#2FCB84` |
| Amber | `#F5A524` | `#FFB84A` |
| Error | `#D92D4A` | `#FF7A90` |
| Outline | `#D5DBE6` | `#263148` |

- Fonts: **Barlow** (Regular, Medium, SemiBold, Bold) for text and **Barlow Condensed** (Medium, SemiBold, Bold) for times, numerals and headings.
  Bundle the TTFs from the mobile repo as app assets. Sentence-case labels, no all-caps eyebrows, content left-aligned.
- Shapes: strip 2 px radius with a 1 px outline and a coloured 10 px tab on the left; menu tiles 10 px; dock 24 px on top; buttons 8 px.
  Plain ink header with the logo, no gradients, no decorative lines, no icon grid.
- The dock is always dark ink, with the Flight / Timer / Photos switch as a segmented control; the start button is a green circle that becomes a red stop square.
- A desktop window is wide: keep the mobile single-column layout in a centred column of at most about 520 px, or use two columns (Home content and dock) at wide sizes. Start with the single column.

---

## 6. Settings kept locally
Timer countdown buffer, training mode (not kept: off at every start), dismissed announcement ids, cached profile, tour seen, last position-queue state.
Secrets (Firebase refresh token) go in the Windows credential store (`PasswordVault`), not in plain files.

---

## 7. What is different from the mobile app
- Replaced: GPS accuracy, battery, location permission, wake lock/keep-awake, Android/iOS settings shortcuts, push (FCM), Play Billing/StoreKit
  subscriptions (the simulator client needs no subscription), the iOS back-swipe, share sheets (use the Windows share/save dialogs).
- Position and time come from the simulator and the PC clock; the pre-flight clock check therefore matters (PC clock vs network time).
- No hangar-flyer app link on Windows for now (the flyer opens the website); optionally register a custom URI scheme later.

---

## 8. Milestones (each ends with passing tests and a runnable build)
1. **M0 Solution split and CI.** Core and Core.Tests projects, the existing app builds on them; GitHub Actions: `dotnet test` on Linux for Core, `dotnet build` (and MSIX publish via the existing PowerShell script) on `windows-latest`.
2. **M1 API client, models, auth, cached start.** Port `AirsportsApi`, `Models`, JSON tests, token refresh/retry, profile, `get_current_sim_navigation_task`, parallel start, platform headers.
3. **M2 Tracking core.** Position source interface, durable queue, uploader with backoff, track log, sessions, 4 h/12 h/window-closed rules; tests ported.
4. **M3 Home and flight deck.** Design tokens, fonts, flight strip, tiles, dock, receiving/scoring status, timer, stop confirmation.
5. **M4 Flights.** My flights, cancel (dialog), Register today and web pages in WebView2, announcements, flight orders, share link, score.
6. **M5 Training, pre-flight, history/GPX.**
7. **M6 Photo observations.**
8. **M7 Shell.** Tour, back button, version line, debug view, minimum version, crash reporting, account deletion.
9. **M8 Polish and release.** Accessibility (keyboard, narration), high contrast, small windows, MSIX packaging and Store submission, `documentation/mobile_changelog.md` entry.

Acceptance for a milestone: the ported tests pass, the screens match the mobile app's behaviour and wording, and a manual run in MSFS against the
production backend works (a flight is tracked, the server shows positions, scoring starts).

---

## 9. Backend changes needed (small; do them in the backend repo, or ask)
- `display/services/mobile_app_activity.py`: accept `msfs` as a platform (today only `android` and `ios`), and show it in the admin "Mobile apps" tab (`MobileAppsPanel.tsx` maps platform labels). `MobileAppActivity.platform` choices need `("msfs", "MSFS client")` and a migration.
- `mobile/config` (`display/views.py::mobile_config`) and `PlatformConfig`: add an `msfs` block (`min_version`, `latest_version`, `store_url`) and settings `MOBILE_MSFS_*` for the update-required gate.
- Confirm `get_current_sim_navigation_task` returns the same extra fields as the app endpoint (score, flight_order_path, training_*), which it should (same formatter); add a test if not covered.
- Add a line to `documentation/mobile_changelog.md` (a new dated section, App part: "MSFS client") for each milestone that ships.

---

## 10. Conventions for the agent
- Match the existing code style of the msfsclient repo; keep `GEMINI.md` accurate (add Core/Tests and the new services).
- Commit in small steps with the milestone in the message; run `dotnet test` before each commit.
- Never hard-code secrets; the Firebase web API key already in the client is public by design.
- Text shown to pilots is plain sentence case, no jargon, no exclamation marks; copy the wording from the Kotlin screens.
- When the Kotlin reference and this plan disagree, the Kotlin code and its tests win; tell the maintainer so this file can be fixed.

## 11. Open questions for the maintainer
- Keep one window or add a compact mode for use beside MSFS (a second monitor or a small always-on-top window)?
- Google and Apple sign-in on Windows: needed, or email and password only?
- Should a flyer link open the client (custom URI scheme), or stay a browser page?
- Which crash reporter (Sentry vs Application Insights)?
