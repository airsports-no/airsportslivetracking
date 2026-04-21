---
layout: ../../layouts/DocsLayout.astro
title: "Contestant Guide: Participating in an Event"
---


# Contestant Guide: Participating in an Event

As a pilot or crew member, your primary interaction with Air Sports Live Tracking (ASLT) occurs through the mobile app. This guide explains how to properly configure your device, understand your flight order, and manage your participation.

---

## 1. App Installation and Identity Management

ASLT uses a secure, passwordless authentication system powered by Google Firebase.

### Installation
*   **Android:** Download "Air Sports Live Tracking" from the Google Play Store.
*   **iOS:** Download "Air Sports Live Tracking" from the Apple App Store.

### Registration and Login
1.  **Email Entry:** Enter your primary email address. 
2.  **Magic Link:** Check your email for a verification link. 
3.  **Critical Rule:** You **must** open this link on the **same mobile device** where the app is installed. If you open the link on a desktop, it will not authenticate your phone.
4.  **Subscription:** Tracking is a premium feature requiring a small annual subscription to cover high-performance server resources. Manage this through your platform's store.

---

## 2. Simply Flying a Pre-Created Flight

In many professional events, the Contest Manager handles all the setup. Your role is simply to ensure your device tracks the flight correctly.

### Receiving Your Flight Order
Once the manager finalizes the schedule, you will receive an email containing:
*   **Maps:** Digital renderings of the route waypoints and gates.
*   **Route Information:** Coordinates and expected leg times.
*   **Scheduled Takeoff Time:** Your precise allocated slot.

### The "Adaptive Start" Logic
ASLT uses a highly sophisticated **Adaptive Start** to accommodate pre-flight delays.
*   **Flexibility:** You have a **2-hour window** (1 hour before to 1 hour after your scheduled time) to cross the Start Gate.
*   **Synchronization:** Your flight scoring is synchronized based on the **actual time** you cross the start line.
*   **Why it Matters:** If you are delayed by 5 minutes due to ATC, you are not penalized. The system simply "shifts" your planned gate times by those 5 minutes, ensuring your navigation scoring remains fair relative to your actual start.

### Device Synchronization (Critical)
*   **Android Users:** You MUST ensure your phone time is accurate. Android devices can drift by several seconds. It is highly recommended to use an app like *Atomic Clock* or verify your system clock against *Time.is*.
*   **iOS Users:** Apple typically handles time synchronization automatically with high precision, but it should still be verified before major events.

---

## 3. Self-Registration and Management

If the event allows "Self Management" (configured by the Contest Manager), you can register yourself.

### Step 1: Join the Contest
1.  Open the app and find the event on the **Global Map**.
2.  Tap the event icon and select **"Join Contest"**.

### Step 2: Schedule Your Flight
Once you have joined the contest, you can schedule yourself for any available Navigation Task. The frontend handles both your team registration and flight scheduling in a single, unified process:

1.  Select the **Navigation Task** you wish to fly.
2.  Tap **"Schedule Flight"**.
3.  **Complete the Registration & Scheduling Form:**
    *   **Co-pilot (optional):** Select your partner from the registered pilots list.
    *   **Aircraft Registration:** Type or select your aircraft (e.g., LN-ASL).
    *   **Airspeed:** Enter your planned airspeed in knots.
    *   **Club:** Enter your flying club name.
    *   **Flight Details:** Specify your **Starting Point Time**, **Wind Speed**, and **Wind Direction**.
    *   **Adaptive Start:** Toggle this ON if you want the system to automatically synchronize your start based on your actual gate crossing (highly recommended).
4.  Tap **"Schedule"**. The system will automatically register your team (if not already done) and allocate your slot.
5.  Your **Flight Order** and maps will be generated and emailed to you automatically within minutes.

---

## 4. Troubleshooting Tracking
If your track "freezes" or disappears:
*   **Battery Optimization:** On Android, ensure ASLT is set to **"Don't Optimize"** or **"Unrestricted"**. Huawei, OnePlus, and Samsung devices are notorious for killing background tracking apps.
*   **Location Permissions:** Ensure the app has **"Always Allow"** location access, not just "While Using the App".
*   **Lead Time:** Tracking only begins during your "Tracker Lead Time" (typically 15-30 minutes before takeoff). If you try to test it hours before, it will not record.
