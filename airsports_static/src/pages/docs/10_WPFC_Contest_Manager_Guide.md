---
title: 'WPFC Contest Manager Guide'
description: 'A comprehensive operational manual for organizers managing a fully managed World Precision Flying Championship on Airsports.no.'
layout: ../../layouts/DocsLayout.astro
---

# World Precision Flying Championship: Contest Manager Guide

This guide is intended for the technical organization team running a **fully managed** World Precision Flying Championship (WPFC) using the Airsports.no platform. In a fully managed competition, pilots focus solely on flying; the organizers handle all route design, team registration, tracker allocation, scheduling, and live scoring.

Before proceeding, ensure your team is familiar with the basic platform concepts outlined in the [Contest Manager Guide](./03_Contest_Manager_Guide).

---

## 1. Glossary of Terms

To navigate the Airsports system effectively, you must understand the specific terminology used throughout the platform:

*   **Team:** The foundational roster entity. Consists of a Pilot, an optional Co-Pilot, an Aircraft (registration), and a Club (for WPFC, this represents the Nation).
*   **Contestant:** A single instance of a Team assigned to fly a specific Navigation Task. (One Team becomes many Contestants over a multi-day championship).
*   **Contest:** The overarching digital container for the entire event (e.g., "WPFC 2026").
*   **Route:** The geometric blueprint created in the Route Editor, defining waypoints, gates, corridors, and secret markers.
*   **Navigation Task:** A live-tracked flight event created from a Route. Assigning Teams to a Navigation Task is what generates Contestants.
*   **Results Service:** An optional integrated system for scoring additional tasks and tests such as planning and observation, and landings.
*   **Task (Results Service):** A top-level scoring container. Can be automatically generated (like a Navigation Task) or manually created (like a Landing Task).
*   **Test (Results Service):** A specific, individually scored component within a Task (e.g., the "Observation" test within a Navigation Task, or the "Flaps" test within a Landing Task).
*   **Scorecard:** The mathematical rule set attached to a Navigation Task that defines penalties, and grace periods for crossing gates.
*   **Flight Order:** A generated document for a Contestant containing map segments, start times, and auto-generated turnpoint/observation photos.
*   **Visibility System:** The three-tier access control for Contests and Tasks: *Private* (organizers only), *Unlisted* (accessible via direct link only), and *Public* (searchable on the main dashboard).
*   **Flymaster:** The dedicated hardware GPS trackers and associated backend service utilized for high-fidelity live tracking.
*   **Traccar:** The backend, open-source geospatial tracking engine used by Airsports to securely store and process all raw GPS data from the apps and other hardware trackers.
*   **GPX / KML / MBTiles:** Standard geographic files. GPX is used for manual track uploads; KML for importing route paths; MBTiles for uploading custom, georeferenced background maps.
*   **Kubernetes:** Resource management system running the airsports application in google cloud.
*   **Kubernetes Calculator:** The backend microservice that spins up dynamically for each individual flight to calculate live scores.
*   **Secret Gate:** A hidden timing/track gate placed on a route to verify pilot track discipline without revealing the exact location on the public map.

---

## 2. Core Architecture & Data Integrity

The system separates the competitors (Teams) from the specific flights they undertake (Contestants). 

> **⚠️ Data Integrity and Mid-Competition Aircraft Swaps**
> A Contestant is a direct, active link to the underlying Team object, not a static copy. If you edit a Team's profile (e.g., changing the Aircraft registration due to a mechanical breakdown) midway through the competition, that change will retroactively update the aircraft listed for all *previous* tasks that Team has flown. 
> 
> *Is this a problem?* For scoring, no. While it breaks the historical accuracy of which specific airframe was used on Day 1, it is the correct operational workaround. Updating the aircraft on the Team profile ensures the Scheduling Assistant correctly prevents aircraft conflicts for all *future* tasks.

---

## 3. The Organizer Workflow Strategy

Setting up a WPFC involves both parallel and sequential tasks.

### Phase 1: Independent Preparation (Days/Weeks Before)
1.  **Create the Contests:** Set up the empty shells for your competitions. Include official FAI logos and header images.
2.  **Design the Routes:** Use the route editor to design the physical flight paths. Routes are independent blueprints. *Tip: You can import KML files if your route was designed in an external GIS tool.*

### Phase 2: Sequential Setup (Days Before)
1.  **Register Teams:** Enter the finalized Pilot, Aircraft, and Nation data into the Contest.
2.  **Create Navigation Tasks:** Combine your Routes and your Contest to generate the specific tasks. Assign your Teams to these tasks as Contestants.

### Best Practice: The "Training Contest"
Create **two** separate contests:
1.  **A Public Training Contest:** Create this early to allow pilots flying training routes to familiarize themselves with the system and test their hardware. This is also a great tool for the contestants to review their own training flights afterwards.
2.  **The Main WPFC Contest:** This contest can be set to Public, but **ensure all Navigation Tasks within it are set to Private** until you are ready to publish the task to the competitors post-briefing.

---

## 4. Registering Teams & Configuring Tracking

The **Team Registration Wizard** establishes the link between the pilot, the aircraft, and the tracking hardware. 

1.  Navigate to the **Teams** section inside your Contest and click **Add New Team**.
2.  Input the Pilot, Co-Pilot (if applicable), Aircraft, and Club. For the world championship the club might well be the nation the contestant is competing for, otherwise it will be the local club were the pilot is a member.
3.  **Planned Airspeed:** Set the default planned airspeed (this can be manually overridden per task if required).
4.  **Configure the Tracking Service:** 
    *   Select **Flymaster** as the service. 
    *   Simply enter the physical **Flymaster Device ID** (printed on the back of the tracker) into the configuration field. *No separate logins, FAI API tokens, or app pairings are required.* This can also be overridden when creating the contestants, but for ease of views we recommend keeping the same tracker for a team throughout the competition.

---

## 5. Route Design & Map Visibility

The built-in Route Editor handles complex mathematical structures like scoring gates, corridors, and specific turn procedures.

### Map Backgrounds and Georeferencing
*   **Standard vs. Custom Maps:** You can upload official FAI/competition maps as MBTiles. Because these are georeferenced, the route you draw digitally will perfectly match the paper map given to the pilot. Unfortunately these maps are not yet available as background maps in the route editor.
*   **Hiding the Background:** Before publishing a task to the public, you can choose to hide the background map in the live viewer. This makes the live track less useful for competing pilots trying to glean geographical hints, while still allowing spectators to watch the flight.

### Key Route Markers
*   **Photo Markers:** Adding a Photo Marker marks the coordinates for ground truth observation. 
*   **Secret Gates:** Placed to ensure pilots maintain track discipline. These are displayed on the live map unless the organizer has explicitly elected to keep secret gates hidden. In this case the penalty appears in the contestant's score log table, but **no annotation is placed on the map**. The exact location remains protected.

---

## 6. Printing Maps & Flight Orders

Airsports provides robust tools to generate and print the physical navigation maps and flight orders used by the pilots.

### The Navigation Map Generator
Organizers can print high-quality maps at any desired scale.
*   **Map Sources:** Choose from pre-existing specialized maps for Nordic countries, generic servers (OpenStreetMap, OpenCycleMap), or your own uploaded custom MBTiles.
*   **Customization:** You retain full control over how the map is displayed, including line colors, line thickness, and route markers.

### Generating Flight Orders
A "Flight Order" is a generated document containing start information, the route map, and optionally, observation photos. It is primarily intended for self service to allow pilots to register for a task and flight without the help of an organizer. A dedicated configuration page lets you dictate exactly how much of the task is "pre-drawn" for the pilot.
*   **Preparation Levels:** You can configure the map to be entirely blank (requiring the pilot to manually plan and draw everything) or fully pre-made, complete with pre-calculated minute marks along the track line.
*   **Auto-Generated Photos:** The system can automatically generate Turnpoint and Observation photos by pulling imagery from Google Aerial Photos based on your Route Markers.

### Best Practices for World Championships
*   **For Training Flights:** Organizers should absolutely experiment with the Flight Order generator. The fully pre-made charts and auto-generated Google Maps photos are excellent for practice flights, allowing pilots to train on observation techniques even if the satellite imagery isn't perfect.
*   **For the Official WPFC Tasks:** **Do not use the auto-generated Flight Order photos for the official competition.** Google Maps imagery does not meet the strict FAI ground-truth requirements. For the real championship tasks, organizers will typically compile their own official Data Packages. You can simply use Airsports to export the bare navigation map (without pre-calculated annotations) to include in your official FAI briefing packets. It is also of course an option to create the navigation maps in another tool than airsports and just use airsports for the live tracking functionality.

---

## 7. Scorecards & Penalties

When you use a Route to create a **Live Tracking Navigation Task**, you must define the rules of the flight.

*   **The Scorecard Library:** Select a scorecard template from the platform's library (e.g., the latest official Precision Flying scorecard). This defines penalty points per second early/late, corridor boundaries, etc. Selecting the scorecard is part of the wizard when creating a navigation task. There are two ways of creating a navigation task:
    
    1. Directly from the contest. This provides the greatest control.
    2. From the list of created routes in the route editor.
    
*   **Modifying the Scorecard:** Organizers can edit the scorecard in the task settings to tweak specific penalty weights or adjust the grace period (time tolerance) for crossing a gate.
*   **⚠️ The Rule of Modification:** Modifying a scorecard **will NOT affect any previous or ongoing flights.** The new rules and grace periods apply only to *new* contestants added and *new* flights started after the save.

---

## 8. The Scheduling Assistant & Manual Control

The **Scheduling Assistant** automates complex logistics, but organizers retain absolute control over every single flight.

### Automated Scheduling
1.  Define the **First Takeoff Time** and desired start/finish intervals. 
2.  **Conflict Resolution:** The system automatically analyzes Team Registration data to guarantee that an **Aircraft**, a **Crew Member**, or a **Tracking Device** is never scheduled in two places at once, enforcing minimum turnaround times.
3.  **Final Optimized Schedule:** An optional linear optimizer to find the most compact timeline possible (review carefully as edge cases can fail).

### Manual Contestant Control
Even after the Scheduling Assistant has completed its optimization, you have full manual control over the schedule.
*   **Dragging and Locking (🔒):** Manually drag a contestant to adjust their slot. Double-click a flight to Lock it. *(Flights are automatically locked (📡) the moment their live tracking calculation starts).*
*   **Recalculating:** After locking specific flights, update the "Next Takeoff Time" and click "Run Scheduler" to re-shuffle unlocked flights around your changes.
*   **Editing Contestants:** You can explicitly edit any contestant to manually override their Takeoff Time, Planned Airspeed, or specific tracking hardware information.
*   **Creating / Deleting Contestants:** You can manually delete or add a contestant at any time. **Note:** Any manually added contestant must still be linked to a pre-registered Team. If a new crew signs up at the last minute, you must first register them as a regular Team in the Contest before you can create them as a Contestant in the Navigation Task.

---

## 9. Competition Day Procedures

To ensure a smooth competition day, follow these sequential steps for scheduling, tracking, and monitoring flights.

### Morning Preparation & Scheduling
*   **Verify Registrations:** Make sure that all teams have been registered. This step assumes that the route and the navigation task have already been created.
*   **Run the Scheduler:** Use the Scheduling Assistant to schedule all contestants in the task according to the plan for the day. You must take into account the expected wind and the planned takeoff time for the first contestant when setting up the schedule.
*   **Data Packages & Maps:** The navigation task map can be exported from the navigation task in Air Sports and included in the Data Package. Alternatively, it can be exported from any other tool designed by the organizers. Because the route editor uses regular GeoJSON to define the route, it is possible to open this in other tools such as QGIS to extract the route elements for use in any separate map application.

### Tracker Handout & Activation
*   **Hardware Verification:** Organizers should verify that each contestant has the correct tracking number. Make sure that the trackers are charged and available in the package delivered to each contestant.
*   **Switch-On Instructions:** There should be a clear instruction regarding when the tracker should be switched on. Ideally, this is at the tracker start time, which can be seen for each contestant in the navigation task details page. The earlier this time is relative to the takeoff time, the easier it is to see if there are any issues with the tracker that will prevent live tracking.

### Live Monitoring & Debugging
*   **The Green Dot:** The primary thing to look for is that the red dot next to the contestant name turns green. This indicates that the calculator has started.
*   **Map Confirmation:** Shortly after this, within a few minutes, the contestants should appear on the live tracking map. At this point, you can be quite confident that the flight will proceed correctly.
*   **Advanced Debugging:** There is some debug low-level functionality available on the navigation task page where it is possible to stop and restart a calculator by clicking on the red or green light. **Warning:** This should not be done unless the organizer fully understands what this entails.

### Post-Flight & Error Handling
*   **Automated Scoring:** Once the flight has completed, there is nothing else to do. The scores should be readily available.
*   **Manual Recovery:** If there is an error, the organizers should export the track log from either the Flymaster tracker or any other standalone tracker the pilots have included, and try to upload this to the contestant once the calculator has stopped. Air Sports will then recalculate the contestant with the updated track data.

#### Incorrect Speeds or Takeoff Times
If a contestant flies at a different time or speed than registered, live scoring will be incorrect.
*   **The Fix:** Delete the contestant from the task, and recreate them using the correct, as-flown speed and takeoff time.
*   **Data Retention:** Raw GPS data in Traccar is tied to the Flymaster Device ID. When you recreate the contestant and recalculate, the system automatically pulls the existing flight data and scores it against your corrected parameters.

#### Network Outages & Manual Uploads
*   **Flymaster Buffering:** If live cell coverage drops, the Flymaster internally buffers positions and automatically uploads the backlog once coverage is restored.
*   **Complete Tracker Failure:** If live data is completely lost, download the raw GPX/IGC file from a backup tracker or the Flymaster's internal SD card. Navigate to the contestant's details page and use the **Manual Upload** function. 
---

## 10. The Results Service (Scoring Procedures)

The platform utilizes a **Penalty Point** scoring system (lowest score wins, 0 is perfect). *Note: The Results Service is optional. Organizers using third-party scoring software can use Airsports strictly as a live tracking engine.*

### Setting up Tests within Tasks
While Navigation Tasks are auto-created from the route, you must configure the manual scoring **Tests**.
1.  **Navigation Tasks:** Open the auto-created task. Manually add Tests for the paper **Planning** exercise and the **Observation** photo penalties.
2.  **Landing Tasks:** Create a new Landing Task, then add four separate Tests inside it: *Engine-on*, *Idle*, *Flaps*, and *Over-Obstacle*.

### Inline Scoring & Real-Time WebSockets
Scores for manual tests are entered directly into the Results Service table cells. The table is powered by WebSockets. The moment you type a score and click away, the data is pushed to the server and instantly broadcast to **all open instances globally**.

*   **Landing Tasks:** Judges typically open the web page on a tablet directly from the landing line, entering penalty scores inline as each aircraft touches down.
*   **Observation Tasks:** After the flight, a judge compares the pilot's paper sheet against the ground truth photos. The resulting penalty score is typed into the Observation test column.
*   **Strategic Delay:** Because the table immediately updates public screens, organizers may want to withhold final manual scores until the end of the day to build suspense.

---

## 11. Handling Discrepancies & Errors

### Batch Updates (Weather Delays and Wind Shifts)
If morning fog rolls in or the competition director announces a wind component change, you do not need to edit flights one by one.
*   Navigate to the **Batch Update** page for the Navigation Task.
*   Select the affected contestants.
*   **Time Shifts:** Apply a time shift (e.g., +60 minutes) to all selected contestants. This is perfect for weather delays—it preserves the staggered starting order and intervals perfectly, simply shifting the entire block of flights forward in time.
*   **Wind Updates:** You can similarly update the wind speed and direction for a block of selected contestants.

### Low-Level Score Overrides (The Gates Page)
In rare instances where the automated scoring engine makes a significant miscalculation, organizers can intervene at a granular level. 
*   Navigate to the Navigation Task table and click the link in the **Gates** column for a specific contestant. 
*   This page displays a detailed breakdown for every gate in the route, comparing planned vs. actual passing times, and lists all penalties applied to the *leg following* that gate.
*   **Removing Penalties:** From this page, you can manually *remove* individual penalties for specific legs. 
*   **⚠️ Limitation:** You can *only* remove penalties. The system does not allow you to manually add or apply new penalties from the Gates page.

---

## 12. Sharing with the Public

Organizers will want to share the live event with spectators, national team members, and remote fans.

*   **The Mission Dashboard:** There are no complex sharing menus. Simply navigate to the public contest page (the Mission Dashboard) in your browser, copy the URL from the address bar, and share it on social media, official websites, or directly with commentators.
*   **Hangar Flyers:** For self-service or local training flights (outside of the formal WPFC structure), organizers can print a "Hangar Flyer" for a specific navigation task. This printed flyer includes a QR code allowing prospective local pilots to scan and sign up for an unofficial fun flight.

---

## 13. Post-Competition: Finalizing & Exporting

When the competition day wraps up, the system provides tools to formalize and export the data.

*   **Task Finalization:** There is no formal "Lock" button to close a task. A Navigation Task automatically displays as "Finalized" in the user interface once its scheduled Finish Time has passed. *(Note: Technically, the platform will still accept late flight tracking, but the UI visualizes the task as complete).*
*   **Exporting Results:** On the Results Service page, click the **Export to CSV** button to download the finalized leaderboards. This CSV data can be passed to external systems, used for official FAI record-keeping, or archived.
*   **Printing Schedules:** In the Scheduling Assistant, you can use the built-in print functionality to generate a visual Gantt chart of the staggered starts, as well as a chronological timetable. These are excellent resources to print and hand out at the morning pilot briefing or to the flight line marshals.