---
layout: ../../layouts/DocsLayout.astro
title: "Route Creation and Task Configuration"
---


# Route Creation and Task Configuration

The most critical part of an air sports event is the **Route**. A route is more than just a list of waypoints; it is a complex mathematical structure that defines the scoring gates, the corridors, and the rules of the flight.

---

## 1. Creating a Route with the Editor

ASLT includes a built-in, browser-based route editor. 

### Route Markers and Special Points
The editor supports various markers to enrich the navigation task:
*   **SP (Start Point):** Typically an "Extended Line" or a "Circle". Crossing this line activates the flight clock.
*   **TP (Turn Point):** A waypoint where the pilot must turn. You can define if a "Procedure Turn" (e.g., 90 degrees out then back) is required.
*   **FP (Finish Point):** The final gate. Crossing this stops the scoring clock.
*   **Secret Gates:** You can place gates along a leg that are not shown to the pilots. These are used to verify if a pilot is following the track line instead of "cutting corners".
*   **Photo Marker:** A special marker used for observation tests.
    *   **Purpose:** These markers represent ground targets or features that a pilot must identify.
    *   **Integration:** When added to a route, the system automatically extracts a high-resolution aerial photo of the coordinates.
    *   **Flight Order:** In the generated Flight Order PDF, these photos are included as a separate observation sheet, providing pilots a clear visual reference of the ground features they are tasked to find.

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
Once a task is created, use the **"Test Calculator"** button. This allows you to upload a sample GPX file to see how the system would score it before you invite real contestants to fly.
