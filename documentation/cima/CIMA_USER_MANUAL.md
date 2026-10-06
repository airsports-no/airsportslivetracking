# CIMA Task Support User Manual

This manual provides step-by-step instructions for creating and running each CIMA task type using the Air Sports Live Tracking platform.

---

## 0. The Pilot Declaration Interface

For tasks requiring pilot input (Speeds or Sequences), organizers must use the **Pilot Declaration** tool.

1.  Navigate to the **Navigation Task Detail** page.
2.  Locate the contestant in the list.
3.  Click **Actions** -> **Pilot Declaration**.
4.  The interface provides two tabs:
    *   **Leg Speeds:** Enter ground speed (kts) for each leg.
    *   **Point Sequence:** (For Contract Nav) Drag-and-drop or use buttons to define the visit order of free waypoints.
5.  Click **Save Changes** to update the contestant's target times and flight plan.

---

## 2.A1 / 2.A2: Curve & Precision Navigation (Declared Speeds)

**Objective:** Fly a predefined route (curves or straight legs) at pilot-declared speeds.

### 1. Route Creation
*   Open **Route Editor**.
*   Place **Start Point (SP)**, **Turnpoints (TP)**, and **Finish Point (FP)** using the *Point* tool.
*   For 2.A1 (Curve), ensure segments are set to "Curved" in the sidebar.

### 2. Pilot Configuration
*   Use the **Pilot Declaration** -> **Leg Speeds** tab.
*   Enter the ground speed for each leg starting from the Start Point.
*   The system calculates required gate times based on these speeds and current task wind settings.

### 3. Running & Scoring
*   **Scoring:** Standard timing penalties apply at each gate.
*   **Live Map:** Shows the route and updated arrival estimates based on declarations.

---

## 2.A3: Contract Navigation

**Objective:** Fly a route with fixed SP, MP (Middle Point), and FP, visiting a set of "Free Points" in a pilot-declared order and speed.

### 1. Route Creation
*   Open **Route Editor**.
*   Create the "spine": **SP**, **MP**, **FP**.
*   Add **Free Points** using the **Free Pt** tool (Flag Icon).

### 2. Pilot Configuration
*   Use the **Pilot Declaration** tool.
*   **Sequence Tab:** Select the Free Points in the intended order of visit.
*   **Speeds Tab:** (Optional) Set speeds for the legs connecting these points.

### 3. Running & Scoring
*   **Scoring:** 
    *   Points are awarded for visiting free points in the **exact declared order**.
    *   Standard timing penalties apply for the fixed gates (SP, MP, FP).
    *   The points awarded per free waypoint are defined in the **Task Scorecard** (`Free Waypoint Score`).

---

## 2.A6: Turnpoint Hunt

**Objective:** Visit as many free waypoints as possible within a time limit (no fixed order).

### 1. Route Creation
*   Open **Route Editor**.
*   Place **SP** and **FP**.
*   Add multiple **Free Points** using the **Free Pt** tool (Flag Icon).
*   *Note:* Individual point scores are no longer set in the editor.

### 2. Task Configuration (Scorecard)
*   Open the **Scorecard** for the task.
*   Set the **Free Waypoint Score** value (e.g., 100 points). This value applies to all free points in this task.

### 3. Running & Scoring
*   **Scoring:** The system awards the scorecard value for every unique free point visited (within default 500m radius).
*   **Live Map:** Free points appear as blue markers.

---

## 2.A7: Circle Task

**Objective:** Fly a circle around a center point within a specific radius range.

### 1. Route Creation
*   **Center:** Use the **Circle** tool to place the **Circle Center**. Set the **Radius** (m) in the sidebar for visualization.
*   **Entry:** Add a point and set type to **Circle Entry**.

### 2. Running & Scoring
*   **Execution:** Scoring starts when the **Circle Entry** is crossed and ends upon the next crossing (after 360 degrees).
*   **Scoring:** Uses the radius ratio formula `P = (Rmin / Rmax - 0.5) * Factor`. 
*   **Parameters:** `Circle Performance Factor` and `Circle Altitude Tolerance` are configured in the **Scorecard**.

---

## 2.A8: Precision Navigation (ANR)

**Objective:** Navigate a corridor with speed sections.

### 1. Route Creation
*   Enable **Show Corridor** in Sidebar settings.
*   Mark segments as speed sections using **Speed Section Start** and **Speed Section End** point types.

### 2. Running & Scoring
*   **Scoring:** Penalties for corridor exit and speed deviations.

---

## 2.B1: Split Square

**Objective:** Fly a precision square with an optional "bonus" free waypoint.

### 1. Route Creation
*   Create square using **TP**s.
*   Add bonus point using **Free Pt** tool.

### 2. Pilot Configuration
*   Use **Pilot Declaration** -> **Sequence** to include the bonus point in the flight plan.

---

## 2.B3: Duration

**Objective:** Fly as long as possible between takeoff and landing.

*   **Setup:** Route with **Takeoff** and **Landing** only.
*   **Scoring:** Automatically calculates duration between the two gate passings.
