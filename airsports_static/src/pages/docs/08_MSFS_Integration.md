---
layout: ../../layouts/DocsLayout.astro
title: "MSFS Integration: Virtual Competition"
---

# MSFS Integration: Virtual Competition

The **Airsports MSFS2020 Client** is a bridge application that connects Microsoft Flight Simulator 2020/2024 to the Air Sports Live Tracking platform. It allows virtual pilots to compete in the same precision flying and Air Navigation Race (ANR) tasks as real-world aircraft, with real-time scoring and live leaderboards.

---

## 1. Introduction

The client brings professional-grade competition opportunities to the virtual world. While you fly in MSFS, the application transmits your high-fidelity telemetry directly to our cloud scoring engine.

*   **Platform Sync:** Competitions must be configured and managed through your user account on [airsports.no](https://airsports.no).
*   **Realism:** The platform treats virtual aircraft exactly like real ones, applying the same rigorous scoring rules and timing windows.

## 2. Installation

The Airsports MSFS Client is available on the Microsoft Store for a seamless installation experience.

1.  **Microsoft Store:** [Download from the Microsoft Store](https://apps.microsoft.com/detail/9N4MZBKPDS5X?hl=en-us&gl=NO&ocid=pdpshare).
2.  **Automatic Updates:** The Microsoft Store version ensures you always have the latest scoring logic and feature updates.

## 3. Getting Started

### Sign Up as a New User
If you don't have an account on Air Sports Live Tracking yet, you can create one directly through the client:
1.  Enter your **email** and a **password**.
2.  Click **Signup**. This connects to our Firebase authentication system.
3.  **Validate:** Check your email for a verification link. You must click this link before you can log in.
4.  If you don't see the email, check your spam folder or use the **"Resend verification email"** button in the client.

### Updating Your Profile
New profiles are initially locked for safety. Upon your first login:
1.  A pop-up will inform you that your profile must be updated.
2.  Enter your **First Name** and **Last Name**.
3.  (Optional) Enter your preferred **Aircraft Registration**.
4.  Click **Save Profile**.
5.  Once saved, the **"Start Tracking"** button will become enabled.

## 4. Usage & Tracking

Using the application is straightforward:

1.  **Log In:** Enter your credentials and click **Login**.
2.  **Launch MSFS:** Start Microsoft Flight Simulator and spawn your aircraft at the desired departure airport.
3.  **Connect:** Click **"Start Tracking"**.
4.  **Status:** The client will display **"Connecting..."** and then update with the timestamp of the latest position sent. If the timestamp is increasing, your positions are being recorded successfully.
5.  **Stop:** To end the session, click **"Stop Tracking"** or simply close the application.

## 5. Known Issues

*   **Session Persistence:** You must log in with your email and password every time the application starts; credentials are not currently remembered for security reasons.
*   **SimConnect:** Ensure you are in the cockpit and the simulation is unpaused before clicking "Start Tracking" to ensure a stable SimConnect bridge.

## 6. Join the Community

Don't fly alone! Join hundreds of other virtual and real-world pilots to discuss tactics, find upcoming events, and get technical support in our official Slack workspace.

*   **Slack (General Community):** [Join our Slack Workspace](https://join.slack.com/t/airsportslivetracking/shared_invite/zt-2mmaui668-tEaJvJgoqg7782m3bdTleg)

---

*Ready to fly? Head back to the [Introduction](/docs/01_Introduction) to learn about the different competition types.*
