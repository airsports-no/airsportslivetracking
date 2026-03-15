# Tracking Devices and Integration: Reliable Data Collection

ASLT is designed to be hardware-agnostic. While the mobile app is the primary method of tracking, the system can consume and process data from multiple sources.

---

## 1. The AirSports Mobile App (iOS & Android)

The AirSports app is the most integrated way to track flights.

### High-Performance Tracking
*   **1-Second Intervals:** During an active competition, the app switches to a high-frequency recording mode. 
*   **Adaptive Transmission:** To conserve battery and data, the app only transmits when necessary, but always maintains a high internal recording rate.
*   **Offline Buffering:** If an aircraft flies into a cellular dead zone, the app will continue to record GPS data locally. Once it reconnects to a network, it "burst transmits" the missing points to the server. The scoring engine then backfills the track and updates the results.

### Essential App Settings
To ensure a reliable track, contestants **must** configure their devices:
*   **Always-On Location:** Set location permissions to **"Always Allow"** (not "Only while using the app").
*   **Background Data:** Enable background data usage for AirSports.
*   **Battery Optimization:** This is the most common cause of failure. You **must** exempt AirSports from your phone's power-saving modes. 
    *   *Android:* Settings > Apps > AirSports > Battery > **Unrestricted**.
    *   *iOS:* Settings > General > **Background App Refresh** (must be ON).

---

## 2. Hardware Trackers (Flymaster)

Many organizations prefer the reliability of dedicated aviation hardware. ASLT has a native integration for **Flymaster** devices.

### Using a Flymaster Tracker
1.  **Configure the Team:** In the ASLT Team Manager, change the **Tracker Service** to **"Flymaster"**.
2.  **Tracking ID:** Enter the device's hardware ID.
3.  **Data Ingestion:** ASLT can receive Flymaster data via a direct HTTP POST integration (`/display/flymaster/`).
4.  **Buffering Support:** Flymaster devices are excellent because they have robust internal memory and long battery life. Even if the entire flight is outside cellular coverage, the data can be uploaded post-flight to the ASLT server for scoring.

---

## 3. Network Aggregators (OGN, SafeSky, Traccar)

For events where pilots are not using the app or Flymaster, ASLT can pull data from existing tracking networks.

### Open Glider Network (OGN) & SafeSky
*   **Global Coverage:** If an aircraft is equipped with FLARM, FANET, or another OGN-compatible transmitter, ASLT can ingest its position.
*   **SafeSky Integration:** ASLT can also consume data from the SafeSky network, which aggregates dozens of different tracking sources into one feed.
*   **Caveat:** These services are "best effort" and may have gaps depending on ground station coverage. For official competition scoring, the **AirSports App** or **Flymaster** are highly recommended because they support local buffering.

---

## 4. Manual GPX Upload

As a failsafe, ASLT allows managers to manually upload a track.
*   If a pilot's tracker fails, but they have a backup log from their avionics (e.g., G3X, ForeFlight, SkyDemon), the manager can export a **GPX file** and upload it directly to the contestant's record.
*   The system will process this GPX file exactly like a live track, calculating all penalties and updating the scoreboard.
