---
layout: ../../layouts/DocsLayout.astro
title: "Route Creation and Task Configuration"
---


# Route Creation and Task Configuration

> **New to ASLT?** Read [How ASLT Works](/docs/00_How_ASLT_Works) first. It explains contests, routes, navigation tasks, teams and contestants in five minutes.

The most critical part of an air sports event is the **Route**. A route is more than just a list of waypoints; it is a complex mathematical structure that defines the scoring gates, the corridors, and the rules of the flight.

> Running an **FAI CIMA** microlight task (2.A1–2.A8, 2.B2, 2.B3)? This guide covers the platform's original "Legacy" task types. See the dedicated [**CIMA Task Guide**](/docs/11_CIMA_Task_Guide) for task-by-task route editor steps, contestant declarations, and CIMA's scoring model (raw points scaled against the best pilot).

---

## 1. Creating a Route with the Editor

ASLT includes a built-in, browser-based route editor. 

### Starting a Route
A new route opens with the question **What is this route for?** Choose a task and the **Task Route Guide** opens on it. It lists what the route needs for that task, with a button on each step that starts the tool that places it. When you place the last element of a step with a fixed number of elements, the guide moves to the next step. A step that places a single thing, such as the landing area of 2.B3 or a gate line, ends by itself when you have drawn it. For any other step without a fixed number, press **Done, next step** when you have placed enough. You can close the guide, reopen it with **Task Wizard** in the toolbar, or change the task there; closing it never changes the route. If you would rather work without help, choose **Build without a guide**.

The task you choose is saved as what the route is **made for**. The route list shows it as **Made for**, and shows other tasks the route's content happens to meet as **Also suitable for**. You can also tick task types in the route settings. The list can be filtered by either (**Match routes by**: *Made for* or *Suitable for*).

### Route Markers and Special Points
The editor supports various markers to enrich the navigation task:
*   **SP (Start Point):** Typically an "Extended Line" or a "Circle". Crossing this line activates the flight clock.
*   **TP (Turn Point):** A waypoint where the pilot must turn. You can define if a "Procedure Turn" (e.g., 90 degrees out then back) is required.
*   **FP (Finish Point):** The final gate. Crossing this stops the scoring clock.
*   **Hidden Gates (called secret gates in older material):** Gates along a leg that are not shown to the pilots. They verify that a pilot follows the track line instead of "cutting corners". Choose **Hidden gate** in the toolbar (or the guide's hidden gate step) and click a leg of the route. The tool stays on for more gates until you press Esc. A hidden gate can be placed on a curved leg too.
*   **Photo Marker:** A special marker used for observation tests.
    *   **Purpose:** These markers represent ground targets or features that a pilot must identify.
    *   **Integration:** When added to a route, the system automatically extracts a high-resolution aerial photo of the coordinates.
    *   **Flight Order:** In the generated Flight Order PDF, these photos are included as a separate observation sheet, providing pilots a clear visual reference of the ground features they are tasked to find.

### Modes, Select and Undo
*   **Select** is the normal mode: click a point to select it and drag it to move it. In every placing mode (waypoints, hidden gate, photos, zones, gates, and the guide's tools) a banner over the map says what a click does. Press **Esc**, or the stop button in the banner, to return to Select. Esc is ignored while a text field (such as the route name) has focus: then choose **Select** in the toolbar or use the banner's stop button.
*   **Undo and redo** are in the toolbar (Ctrl+Z, and Ctrl+Shift+Z or Ctrl+Y). A drag is one step.
*   **Adding a waypoint to a leg:** drag the blue dot in the middle of a straight leg. Pressing it without dragging does nothing.

### What Happens When a Leg Changes
A hidden gate lies on one leg and cannot bend the route. If you move, add or delete a waypoint at either end of the leg, or reshape its curve, the hidden gates on that leg are removed, and so are photos that the change makes farther from the route than the maximum observation distance (0.5 NM unless you change it in the settings). A photo that was already out of range before the edit is left where it is. While you drag, the gates and photos that would be removed are shown faded. Afterwards the editor lists what it removed, and **Undo** brings it back.

On a curved leg, a hidden gate splits the curve in two without changing its shape. When a hidden gate is removed, the two parts become one curve again. If you reshaped one part, the joined curve follows the shape you gave it.

### Georeferenced Maps
ASLT supports high-precision map overlays.
*   **Standard Maps:** Built-in satellite and vector maps are available.
*   **Custom Maps (GeoTIFF/MBTiles):** If you have official FAI/club competition maps, you can upload them. These are georeferenced so the route you draw on the editor perfectly matches the paper map the pilot is using. For large map processing, contact `support@airsports.no`.

---

## 2. Attaching a Route to a Navigation Task

A Route is just a collection of points. A **Navigation Task** adds the rules.

### Task Setup
When you create a Navigation Task, you must link:
1.  **A Route:** The physical path.
2.  **A Scorecard:** The specific competition rules and penalties. **The Scorecard automatically determines the Calculator Type** (e.g., Precision, ANR, Poker), so you do not need to select the calculator manually.

### Supported Calculators
*   **Precision Flying:** Focuses on waypoint timing and track deviation.
*   **ANR Corridor:** Focuses on staying within a specified width (e.g., 0.4 NM).
*   **ANR Prohibited Zones:** Uses drawn polygons. Entering a polygon triggers a penalty.
*   **Poker Run:** Special mode where crossing a gate polygon "deals" a card to the contestant's hand.

---

## 3. Specific Requirements for Advanced Task Types

### Pilot Poker Run
To support a Poker Run, your route must have **Gate Polygons**.
*   Standard waypoints are too small for a casual event.
*   Instead of a single line, draw a **Polygon** (a large area) around each target airfield or landmark.
*   When a pilot flies into this polygon, the system registers the "crossing".

### ANR (Air Navigation Race)
*   **Corridor Width:** You must define the width of the corridor in the task configuration.
*   **Rounded Corners:** Check this box if you want the corridor to have a smooth radius at turn points, which is standard for modern ANR events.
*   **Backtracking Logic:** ANR rules usually penalize flying backwards. You can configure the "Backtracking Bearing" in the scorecard.

---

## 4. Finalizing and Testing
There's no separate sandbox mode — you test a task by running a real track through it. Register a contestant on the task (a placeholder one works fine), then choose **Upload GPX** from their action menu on the task detail page. This feeds a GPX file through that contestant's calculator exactly as if they'd flown it, so you can see how the task scores before inviting real contestants — but it first **resets that contestant's existing track and score**, so don't run it against an entrant whose live data you want to keep.
