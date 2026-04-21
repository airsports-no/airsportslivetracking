---
layout: ../../layouts/DocsLayout.astro
title: "Contest Manager Guide: Orchestrating an Event"
---


# Contest Manager Guide: Orchestrating an Event

As a Contest Manager, you are the architect of the competition. ASLT provides powerful tools to handle complex logistics, real-time scoring, and advanced scheduling. 

---

## 1. Establishing Your Contest

To host a contest, you need **Organizer** status. This is **automatically approved** for all registered users.

### Step 1: Activate Organizer Status
1.  Log in to your account at `https://airsports.no/`.
2.  In the navigation bar, click the button labeled **"Become an Organizer"**.
3.  Approval is instantaneous. A new **"Management"** menu will now be visible in your navigation bar.

### Step 2: Create the Contest
1.  Access the **Contest Management Dashboard** by selecting **"My contests"** from the Management menu.
2.  Click **"Create New Contest"**.
3.  **Name & Location:** Provide a descriptive name and geolocation.
4.  **Visibility:**
    *   `is_public = false`: Private setup mode. Only visible to you.
    *   `is_public = true` & `is_featured = false`: Unlisted. Accessible via a direct link.
    *   `is_public = true` & `is_featured = true`: Publicly listed on the global map.

---

## 2. Creating Navigation Tasks

Once a Contest is established, you can create one or more **Navigation Tasks** (e.g., Task 1: Navigation, Task 2: Poker Run). 

Building a Navigation Task requires:
1.  **A Route:** The physical path and gates.
2.  **A Scorecard:** The specific competition rules and penalties.

For detailed, step-by-step instructions on designing routes and configuring task parameters, please refer to:
*   **Guide 04: Route Creation and Task Configuration**

---

## 3. Team Registration and Resource Management

ASLT manages teams based on three key resources: **Crew Members**, **Aircraft**, and **Tracking Devices**.

### Registering Teams
1.  From the Contest Detail page, select **"Teams"**.
2.  **Add Team:** Enter the Pilot and Navigator (Crew 1 & Crew 2).
3.  **Assign Aircraft:** Input the registration (e.g., LN-ABC). 
4.  **Assign Tracker:** Choose "Airsports App" or "Flymaster". Enter the Tracking ID.
    *   *Note: Multiple teams can share the same aircraft or crew member. The scheduler handles this.*

---

## 3. The Flight Scheduler Optimizer (Deep Dive)

Scheduling a 30-team competition with 10 shared aircraft and limited trackers is a complex mathematical problem. ASLT includes an advanced **Linear Programming Optimizer** to solve it.

### Scheduling Parameters
*   **Takeoff Interval (min):** Minimum gap between successive aircraft departures (to ensure safety and separation).
*   **Finish Interval (min):** Minimum gap between successive arrivals (to manage runway occupancy and judge capacity).
*   **Aircraft Switch Time (min):** The time required for a plane to land, taxi, swap crews, and refuel before its next mission.
*   **Crew Switch Time (min):** If a pilot is flying in multiple teams, this is the rest period required between flights.
*   **Tracker Switch Time (min):** The time required to physically move a tracker (like a Flymaster) from one aircraft to another.
*   **Tracker Lead Time (min):** This defines when the system starts recording. For example, a 15-minute lead time means the app starts tracking 15 minutes before the scheduled takeoff.
*   **Planning Time (min):** The time allocated for the crew to prepare their maps and flight plan.

### Using the Optimizer
1.  Go to the **"Contestant Schedule"** tab in your Navigation Task.
2.  Select **"Generate Schedule"**.
3.  **Algorithmic Greedy Solution:** This is the default. It quickly places teams in the first available slot.
4.  **Optimal Solution (Linear Programming):** Checking the **"Optimize"** box activates a mathematically rigorous solver. It doesn't just find *a* solution; it calculates the schedule that minimizes the total duration of the entire contest while respecting every single constraint.
5.  **Frozen Teams:** If a specific team *must* fly at a certain time (e.g., they have a maintenance slot or a VIP departure), you can "Freeze" their time before running the optimizer.

---

## 4. Operational Controls

### Recalculation
Mistakes happen. If a pilot flies a task but later it is discovered that the wind was 10 knots instead of 5, or if a judge wants to re-run the numbers with a different scorecard:
1.  Navigate to the **Contestant Track**.
2.  Adjust the task parameters (e.g., update the Wind Speed).
3.  Click **"Recalculate"**. The system re-processes the entire raw GPS track against the new rules without requiring a re-flight.

### Calculation Delay
To prevent "Live Cheating" (where a crew on the ground could watch a rival's track), you can set a **Calculation Delay**. 
*   A 30-minute delay means the public map and leaderboard only show data that is 30 minutes old.
*   The system still records in real-time but buffers the *display* of the results.

---

## 5. Flight Order Configuration

The Flight Order is the document package (PDF) generated for each contestant. Contest Managers can customize this to fit the specific needs of the task.

### Key Settings
*   **Document Size & Orientation:** Choose between A3 or A4, and Portrait or Landscape.
*   **Map Zoom Level:** The default is **Zoom 12**, which is typically the best balance for navigation maps.
*   **Map Source:** Select from various providers (CyclOSM, satellite imagery, or your own uploaded maps).
*   **Annotations:** You can toggle minute marks and leg headings. When enabled, the generated map provides a "ready-to-fly" experience for the pilot.
*   **Aerial Photos:** You can configure the DPI, the zoom level, and the physical area (meters across) for turning point and observation photos. High-resolution photos help pilots identify targets during the flight.

---

## 6. User Uploaded Maps and Permissions

Organizers can upload their own maps to be used as backgrounds in the tracking map or within the Flight Orders.

### Map Uploads
*   **Formats:** Supports georeferenced map formats.
*   **Size Limit:** The maximum allowed size for map uploads is **100 MB**. For larger maps, consider removing zoom levels or splitting the map into multiple parts.
*   **Recommended Zoom:** Experience shows that **zoom level 12** is typically the best for navigation maps.
*   **Source Preference:** You can set an uploaded map as the primary source for a task's Flight Order, overriding the global map defaults.

### Permissions and Security
ASLT utilizes a granular permission system to protect sensitive data.

*   **Contest Permissions:** 
    *   `change_contest`: Allows a user to edit the contest, manage teams, and run the scheduler.
    *   `view_contest`: Allows a user to see the contest details but not make changes.
*   **Map Permissions:**
    *   **Unprotected Maps:** These are available for any organizer to use in their tasks.
    *   **Protected Maps:** Access is restricted to users who have explicit `view_useruploadedmap` permissions. 
    *   **Automatic Access:** Contest managers can automatically access maps uploaded by other staff members associated with the same contest.
*   **Public vs. Private:** Remember that setting a Navigation Task to `is_public=false` hides the tracks from the global map, which is essential for maintaining the "quarantine" of pilots during a major event.
