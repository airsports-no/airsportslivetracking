# Plan: protect the tracking ID against position spoofing

Status: **not started** (planned 2026-10-10). Nothing here is implemented.

## Problem

`Person.app_tracking_id` is both the identifier and the only credential for sending positions to Traccar (OsmAnd
protocol, port 5055). The app must receive it through the API, so anyone who learns it can spoof position reports for
that pilot. Hardware trackers are worse: the ID is an IMEI (effectively public) and their protocols cannot be signed.

## Threat model

1. **Outsider**: learns a pilot's ID (API leak, logs, shared screen) and injects positions.
2. **Cheating pilot with an accomplice**: the pilot extracts their *own* ID and signing secret from their phone and
   hands them to an accomplice, who flies (or simulates) the route and sends positions as the pilot while the pilot
   stays on the ground or flies a different route. The credential is legitimately issued to the attacker's own
   account, so signing alone does not help: the secret must be bound to the genuine app on a genuine device, and the
   data itself must be checked.
3. **Cheating pilot, single device**: GPS spoofing / mock-location apps on the pilot's own phone.

## Goals / non-goals

- Goal: a leaked app tracking ID alone can no longer inject positions (threat 1).
- Goal: an app ID cannot be spoofed through a hardware-tracker protocol, and a tracker ID cannot be spoofed as an app.
- Goal: make threat 2 hard and detectable: the signing key cannot be exported from the device, only a genuine app on
  an attested device can use it, and a second source for the same pilot is detected.
- Goal: threat 3 raised to "needs a rooted/compromised device or extra hardware", flagged for review when detected.
- Non-goal: *prevention* of every collusion. A pilot with an accomplice who physically carries the pilot's real
  phone can only be caught by data plausibility and organiser rules, not by cryptography.
- Non-goal: authenticating hardware trackers (vendor protocols do not support it). Mitigate server-side only.

## Design

1. **Per-install signing secret**
   - Issue a random secret at sign-in or in `register_device` (see `MobileDevice`, `UserPersonViewSet.register_device`).
   - App stores it in Android Keystore / iOS Keychain. Server stores it hashed or encrypted, linked to the device row.
   - Revoked on sign-out (`unregister_device`), account deletion, and explicit rotation.
2. **Signed reports via a gateway**
   - App sends positions to a verifier instead of Traccar port 5055.
   - Each report carries `timestamp` and `sig = HMAC(secret, id|timestamp|lat|lon|speed|bearing|altitude|...)`.
   - Gateway checks signature, clock-skew window (e.g. +/- 60 s) and a per-device last-timestamp (replay protection),
     then forwards to Traccar on the internal network.
   - Open decision: Django endpoint vs separate thin service in front of Traccar. Must handle 1 Hz per phone
     (see memory: tracking is always 1 Hz) with low latency.
3. **Close the OsmAnd port to the public**; only the gateway reaches it. Hardware tracker ports are unchanged.
   Check the ingress/helm config (`helm/templates/deployment_traccar.yml`, `MOBILE_TRACCAR_URL`).
4. **Pin source by protocol**
   - Traccar positions carry `protocol`. In the processor, accept for app-tracked contestants
     (`TRACKING_PILOT`, `TRACKING_COPILOT`, `TRACKING_PILOT_AND_COPILOT`) only gateway-originated (OsmAnd) positions;
     for `TRACKING_DEVICE` contestants reject OsmAnd.
   - Simulator / MSFS client use OsmAnd with `simulator_tracking_id`: give them signing too or an explicit exception.
5. **Hardware tracker mitigations (server-side)**
   - Bind a tracker to a contestant only for the flight window.
   - Flag implausible tracks (position jumps, impossible speed, two sources claiming one ID).
6. **Optional: per-flight tokens**
   - ID/secret valid only from the tracking window until `finished_by_time`, so a leak is useless after the flight.
   - Needs a change in how positions map to contestants (today: via person, `Contestant.get_tracker_ids`-style lookup).

## Defences against a pilot handing their credentials to an accomplice

Cryptography alone cannot stop this; combine key binding, attestation and server-side detection.

7. **Non-exportable signing key**
   - Generate an asymmetric key pair *on the device* in Android Keystore (StrongBox/TEE, `setIsStrongBoxBacked`) / iOS
     Secure Enclave. Register only the public key with the server; sign each report on-device. Nothing the pilot can
     read out is sufficient to forge reports. This replaces the shared HMAC secret in design item 1 (server then
     verifies a signature, not an HMAC; keep the HMAC variant only as a fallback if per-report signing cost is too high).
   - Use key attestation to prove at registration that the key really lives in hardware.
8. **App and device attestation**
   - Android Play Integrity API (device + app integrity, licensed install), iOS App Attest / DeviceCheck.
     Required at key registration and re-checked periodically (e.g. at session start). Rejects emulators, rooted/
     tampered devices, modified APKs and scripts that replay the protocol.
   - Sideloaded debug builds (current test flow) need an explicit allow-list or a non-prod environment.
9. **One active device per pilot, bound to the flight**
   - Limit the number of registered devices per person (e.g. 2) and require re-authentication to add one; notify the
     pilot (and optionally the organiser) on a new device.
   - Mark which device is the tracking source for a contestant's flight at session start; reject reports from other
     keys for the same contestant, and alert on two concurrent sources (the accomplice plus the pilot's own phone).
10. **Server-side plausibility / collusion detection** (also covers threat 3 and hardware trackers)
    - Kinematic checks: position jumps, impossible speed/acceleration/climb, a track that is too perfect or follows
      the route exactly with no wind drift.
    - Phone sensor consistency: the app sends barometric pressure, accelerometer/gyro summaries and GNSS quality
      (satellite count, C/N0, mock-location flag via `isMock`/`isFromMockProvider`). GPS vs baro altitude and
      motion vs reported speed should agree; GPS-spoofer output usually does not.
    - Cross-check against independent sources where available: the ADS-B / traffic feeds (SafeSky) for the aircraft
      registration, and the pilot's own previously registered aeroplane.
    - Take-off / landing evidence: ground-station or organiser confirmation of take-off time and aircraft.
    - Output a per-flight risk score; flag for organiser review rather than auto-disqualify.
11. **Organiser and rules measures** (non-technical, documented for contest directors)
    - Tracker device lock for high-stakes events: organisers issue hardware trackers or require a named, attested
      device; the device ID is registered per contestant before the flight.
    - Post-flight audit trail: keep signed raw reports, attestation results and device history per flight.
    - Make the cheating risk part of the rules, with a clear sanction and an appeals path for false positives.

Accepted residual risk: an accomplice who holds the pilot's *real, attested* phone and flies the route, or a pilot who
defeats attestation with a compromised-but-passing device. Detection (items 10, 11) is the control for these.

## Steps (suggested order)

1. **Audit exposure**: find every API response/serializer/template that includes `app_tracking_id` (organiser views,
   contestant serialisers, websocket payloads). Stop exposing it to anyone but the owner. Do this first; it is cheap.
2. Decide the gateway location and the wire format (header vs query params; OsmAnd compatibility).
3. Backend: device key registration (public key + attestation verification) / rotation / revocation endpoints,
   model fields, per-person device limit, tests. (Start with HMAC secret only if attestation is deferred, but plan
   for the key-pair design so the wire format does not change.)
4. Gateway service + replay/skew checks + tests, including load test at 1 Hz x expected concurrent pilots.
5. Processor: protocol pinning; simulator/MSFS clients updated.
6. Android app (first, per agreed order), then iOS: Keystore/Keychain storage, signing in the position sender,
   handling "rejected: bad signature / clock skew" (ties in with phone clock-drift detection).
7. Rollout: gateway in **audit mode** (accept unsigned, log) -> app release with signing -> `MOBILE_*_MIN_VERSION`
   bump via `/api/v1/mobile/config/` -> **enforce** -> close port 5055.
   Mirror the `ACCESS_ENFORCEMENT_MODE` audit/enforce pattern in settings.
8. Plausibility / collusion detection (design items 5 and 10) in the processor, in audit mode first, independent of
   the signing work; tune thresholds on past flights to measure false positives before surfacing flags to organisers.
9. App: sensor payload (baro, motion, GNSS quality, mock flag) and Play Integrity / App Attest at session start.

## Risks / open questions

- Legacy apps (`airsports_android`, `airsports_ios`) and third-party OsmAnd clients stop working once enforced.
- Added latency and a new single point of failure on the position path; needs monitoring and horizontal scaling.
- Phone clock drift breaks the skew window; consider server-time sync from the gateway response.
- Secret/key loss (app reinstall, new phone) needs a smooth re-issue flow that does not become the bypass
  (re-issue must require sign-in and, near a contest, a visible notice to the organiser).
- Attestation excludes some legitimate devices (custom ROMs, no Google services, older phones): decide the policy and
  a fallback (organiser-issued hardware tracker).
- Privacy: extra sensor data and device history need disclosure in the privacy policy and minimal retention.
- False positives from plausibility checks can wrongly accuse a pilot; flag, never auto-penalise.
