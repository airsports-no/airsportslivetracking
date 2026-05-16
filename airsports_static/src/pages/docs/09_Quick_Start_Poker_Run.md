---
layout: ../../layouts/DocsLayout.astro
title: "Quick Start: Organizing a Poker Run"
---

# Quick Start: Organizing a Poker Run

A Poker Run is a casual, social flying event where pilots visit various waypoints to collect digital playing cards. The crew with the best poker hand at the end wins. This guide covers everything from initial setup to live scoring.

---

## 1. Create the Contest

Before you can add tasks, you need an overall contest container.

1.  Log in to [app.airsports.no](https://app.airsports.no).
2.  Go to **Management** > **My Contests**.
3.  Click **Create New Contest**.
4.  Enter the name (e.g., "Summer Fly-in Poker Run 2026") and location.
5.  Set the visibility to **Public** if you want it to appear on the global map.
6.  Save the contest.

## 2. Design the Route

The route defines where the pilots will fly and where cards are "dealt."

1.  In your mission dashboard, go to the **Routes** tab.
2.  Click **Create New Route**.
3.  **Add Waypoints:** Click on the map to add the sequence of airports or landmarks. 
4.  **Add Gate Polygons (Optional but Recommended):** 
    *   Switch to the **Add Polygon** mode.
    *   Draw a large area (e.g., around an airfield) for each card-collection point.
    *   Name the polygon exactly the same as the waypoint it belongs to.
    *   *Note: If no polygon is present, ASLT will fall back to a distance-based check (radius of the gate width).*
5.  **Save the Route.**

## 3. Configure the Navigation Task

The task brings the route and poker rules together.

1.  In your contest dashboard, go to the **Tasks** tab.
2.  Click **Add Navigation Task**.
3.  Select your newly created **Route**.
4.  **Select Scorecard:** Choose the **Pilot Poker Run** scorecard. This automatically sets the calculation engine to Poker mode.
5.  Set the **Start Time** and **Finish Time** for the window when pilots can fly.
6.  Save the task.

---

## 4. Participant Setup

### Downloading the App
Contestants must use the **Air Sports Live Tracking** app to record their flight and receive cards.
*   **iOS:** [Apple App Store](https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686)
*   **Android:** [Google Play Store](https://play.google.com/store/apps/details?id=no.airsports.android.livetracking)

### Registration
There are two ways to get pilots into your task:

#### Option A: Self-Registration (Recommended for social events)
1. Ensure **"Allow Self Management"** is enabled in your Task settings.
2. Pilots find the contest on the dashboard at `app.airsports.no`.
3. They click **Register** to enter their details and then **Schedule Flight** to join the task.

#### Option B: Manual Registration
1. As an organizer, go to the **Teams** tab in your contest.
2. Add the pilot and co-pilot details.
3. In the **Contestant Schedule** of the Navigation Task, add the team to a slot.

---

## 5. Live Tracking and Scores

Once the flight window begins, you can monitor the action in real-time.

1.  **Find the Map:** From the contest page on `app.airsports.no`, click on the **Live Map** button next to your Poker Run task.
2.  **View the Hand:** As pilots cross gates, their cards will appear instantly on the map.
3.  **Leaderboard:** The **Results** tab in your contest will show the current hands and estimated poker rankings as pilots land.

---

*Need more detail? Check out the full [Contest Manager Guide](/docs/03_Contest_Manager_Guide).*
