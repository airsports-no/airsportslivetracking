# CIMA Task Catalogue Technical Implementation Design
# CIMA Task Catalogue Implementation Plan

This document serves as a comprehensive technical specification for implementing CIMA task support in the Air Sports Live Tracking application. It provides detailed instructions for modifying data models, implementing scoring algorithms, and updating the user interface.
This document outlines the detailed technical plan to implement support for CIMA (Commission Internationale de Micro Aviation) task types in the Air Sports Live Tracking application. The plan is based on the gap analysis provided in the "CIMA Task catalogue implementation draft".

## 1. Data Model Enhancements
## 1. Core Data Model Changes

### 1.1. Waypoint Class (`src/display/waypoint.py`)
To support the diverse requirements of CIMA tasks (circles, free waypoints, declared leg speeds), the underlying data models need to be extended.

The `Waypoint` class is a plain Python object (pickled in the DB) that acts as the fundamental building block for routes. It must be extended to support the geometry and properties of CIMA tasks.
### 1.1. Waypoint Model (`src/display/waypoint.py`)

**Changes:**
Update the `__init__` method and add the following attributes. Ensure default values maintain backward compatibility.
Extend the `Waypoint` class to support new geometric and logical properties.

```python
class Waypoint:
    def __init__(self, name: str):
        # ... existing attributes ...
        
        # CIMA Extensions
        self.radius: float = 0.0          # Radius in meters (for Circle tasks)
        self.is_circle_center: bool = False
        self.is_circle_entry: bool = False # The point where circle timing starts
        self.is_free_point: bool = False   # If True, this point is not part of the sequential spine by default
        self.is_speed_section_start: bool = False
        self.is_speed_section_end: bool = False
        self.group_id: str | int | None = None # To associate Center with Entry, or Speed Start with Speed End
        self.score_value: float = 0.0      # Points awarded for visiting (for Turnpoint Hunt)
        
        # ... existing methods ...
```
*   **New Attributes:**
    *   `radius` (float): Radius in meters (for Circle tasks).
    *   `is_circle_center` (bool): Identifies the center point of a circle.
    *   `is_circle_entry` (bool): Identifies the entry point for a circle task.
    *   `is_free` (bool): Identifies a waypoint that is part of a "free" set (no fixed order initially, or order defined by pilot).
    *   `is_speed_start` (bool): Start of a speed section.
    *   `is_speed_end` (bool): End of a speed section.
    *   `group_id` (str/int): To group related waypoints (e.g., a specific circle's center and entry point, or a specific speed section).

### 1.2. Route Model (`src/display/models/route.py`)

The `Route` model stores lists of `Waypoint` objects.
*   No schema changes expected as `waypoints` is a `MyPickledObjectField`. The `Route` object will simply store the extended `Waypoint` objects.
*   **Methods:** Update `get_extent` and `validate_gate_polygons` to handle the new waypoint types (e.g., ensure circle centers are not treated as normal gates).

**Changes:**
1.  **`validate_gate_polygons`**: Update this method. It currently assumes all waypoints are sequential gates. It must explicitly skip waypoints where `is_circle_center` is True, as these are reference points, not gates to be crossed.
2.  **Helper Methods**: Add methods to easily retrieve specific task features.
    ```python
    def get_free_points(self) -> list[Waypoint]:
        return [wp for wp in self.waypoints if wp.is_free_point]
    
    def get_circle_configuration(self) -> dict | None:
        # Return dictionary with 'center' (Waypoint) and 'entry' (Waypoint) if present
        pass
    ```

### 1.3. Contestant Model (`src/display/models/contestant.py`)

This model represents the pilot's entry. CIMA tasks require pilots to declare speeds and waypoint ordering *before* flight.
Support for pilot-declared parameters.

**Changes:**
1.  **`declared_configuration` Field**: Add a `JSONField` to store pilot declarations.
    ```python
    # Use JSONField for flexibility. Default to empty dict.
    declared_configuration = models.JSONField(default=dict, blank=True)
    ```
    
    **Schema for `declared_configuration`:**
    ```json
    {
      "leg_speeds": {
        "Gate 1": 45,    // Speed in knots
        "Gate 2": 50
      },
      "waypoint_order": ["SP", "TP3", "TP1", "TP2", "FP"], // For Contract Nav
      "declared_times": {
        "Gate 1": "2023-10-27T10:00:00Z"
      }
    }
    ```
*   **New Field:** `declared_configuration` (JSONField/MyPickledObjectField).
    *   This will store a dictionary containing:
        *   `leg_speeds`: `{ "gate_name": speed_in_knots, ... }` (For 2.A1/2.A2).
        *   `waypoint_order`: `[ "gate_A", "gate_C", "gate_B" ]` (For 2.A3/2.A6/2.B1).
        *   `declared_times`: `{ "gate_name": datetime_iso, ... }` (Alternative to speeds).
*   **Method Update:** Update `calculate_missing_gate_times` to respect `declared_configuration['leg_speeds']` if present, overriding the global `air_speed`.

2.  **`calculate_missing_gate_times` Method**:
    *   Modify this logic to check `self.declared_configuration.get('leg_speeds')`.
    *   Iterate through the route. For the leg starting at `current_gate`, if a speed is found in `leg_speeds`, use it to calculate the duration to the next gate (`distance / speed`).
    *   If no speed is declared for a leg, fallback to `self.air_speed` or `self.predefined_gate_times`.
    *   **Crucial:** Ensure wind correction is applied to the declared *ground* speed if the task specifies declared *airspeed*, or vice-versa. CIMA 2.A1 specifies declared speeds are usually *ground* speed, corrected for wind.
### 1.4. Scorecard Model (`src/display/models/scorecard_and_gate_score.py`)

### 1.4. Scorecard (`src/display/models/scorecard_and_gate_score.py`)
Add configuration for new CIMA-specific penalties.

Add configuration fields for the new scoring mechanics.
*   **New Fields:**
    *   `circle_exit_penalty` (float): Penalty for leaving the circle bounds.
    *   `circle_missed_center_penalty` (float): Penalty for not crossing center/entry correctly.
    *   `speed_section_formula` (str/enum): To select the scoring formula for speed sections.
    *   `missed_free_waypoint_penalty` (float).

**Changes:**
Add the following fields to `Scorecard`:
## 2. Route Editor Changes

*   `circle_performance_factor`: float (Default 500, used in formula `(Rmin/Rmax - 0.5) * factor`)
*   `circle_min_radius_ratio`: float (Default 0.5, below this ratio score is 0)
*   `circle_altitude_tolerance`: float (Default 200 ft/61m)
*   `circle_altitude_penalty`: float (Default 20% of score)
*   `free_point_missed_penalty`: float (Points deducted if a declared free point is missed)
### 2.1. EditableRoute (`src/display/models/editable_route.py`)

## 2. Route Editor & Parsing (`src/display/models/editable_route.py`)
Update the JSON parsing logic in `_create_waypoint_list` to handle new `pointType` values from the frontend.

The `EditableRoute` model stores the raw GeoJSON/JSON definition from the frontend map editor. It needs to parse new `pointType` values into the extended `Waypoint` objects.
*   **New Point Types to Handle:**
    *   `circle_center`: Sets `is_circle_center=True`, reads `radius` property.
    *   `circle_entry`: Sets `is_circle_entry=True`.
    *   `free_waypoint`: Sets `is_free=True`.
    *   `speed_start`: Sets `is_speed_start=True`.
    *   `speed_end`: Sets `is_speed_end=True`.

**Changes:**
### 2.2. Validation
*   Ensure Speed Start has a corresponding Speed End.
*   Ensure Circle Center has a defined Radius.

1.  **`_create_waypoint_list` Method**:
    *   Expand the logic inside the loop that reads `item["properties"]["pointType"]`.
    *   **Case `circle_center`**:
        *   Create Waypoint.
        *   Set `wp.is_circle_center = True`.
        *   Read `wp.radius = item["properties"].get("radius", 0)`.
    *   **Case `circle_entry`**:
        *   Set `wp.is_circle_entry = True`.
    *   **Case `free_point`**:
        *   Set `wp.is_free_point = True`.
        *   Set `wp.score_value = item["properties"].get("score", 100)`.
    *   **Case `speed_start` / `speed_end`**:
        *   Set respective flags.
## 3. Calculator Engine Architecture

2.  **Validation**:
    *   Add validation in `validate_valid_corridor_route` (or a new validator) to ensure:
        *   A Circle Center has a radius > 0.
        *   A Circle Entry exists if a Circle Center exists.
The current `GatekeeperRoute` is designed for strict sequential navigation. To support CIMA tasks, we will introduce specialized sub-calculators that run alongside or extend the main gatekeeper.

## 3. Calculator Engine Implementation
### 3.1. Abstract Calculator Interface

The core logic resides in `src/display/calculators/`. We will create specialized calculator classes.
Define a standard interface for these sub-calculators if `Gatekeeper` doesn't already fully provide one (it has a `calculators` list).

### 3.1. `CircleCalculator` (`src/display/calculators/circle_calculator.py`)
### 3.2. New Calculators (`src/display/calculators/`)

Create a new class `CircleCalculator`.

**State Tracking:**
*   `status`: `WAITING`, `ORBITING`, `FINISHED`.
*   `min_dist`: Float (initialized to infinity).
*   `max_dist`: Float (initialized to 0).
*   `entry_time`: Datetime.
*   `altitude_valid`: Bool (True).
*   `start_altitude`: Float.

**Methods:**
*   `__init__(self, center_wp: Waypoint, entry_wp: Waypoint, scorecard: Scorecard)`
*   `process_position(self, position: ContestantReceivedPosition) -> UpdateScoreMessage | None`:
    1.  **WAITING**: Check if `entry_wp` line is crossed. If yes:
        *   Set `status = ORBITING`.
        *   Set `entry_time = position.time`.
        *   Set `start_altitude = position.altitude`.
        *   Emit `UpdateScoreMessage` (Information: "Started Circle").
    2.  **ORBITING**:
        *   Calculate distance `d` from `position` to `center_wp`.
        *   Update `min_dist = min(min_dist, d)`, `max_dist = max(max_dist, d)`.
        *   Check Altitude: If `abs(position.altitude - start_altitude) > scorecard.circle_altitude_tolerance`, mark `altitude_valid = False`.
        *   Check Exit: Defined as crossing the `entry_wp` line again (or a separate exit line).
        *   If Exit Crossed:
            *   Set `status = FINISHED`.
            *   Calculate Score:
                *   `ratio = min_dist / max_dist`.
                *   If `ratio <= scorecard.circle_min_radius_ratio`: `points = 0`.
                *   Else: `points = (ratio - 0.5) * scorecard.circle_performance_factor`.
                *   If not `altitude_valid`: Apply `scorecard.circle_altitude_penalty` (e.g., reduce points by 20%).
            *   Emit `UpdateScoreMessage` (Score: `points`).

### 3.2. `FreeNavigationCalculator` (`src/display/calculators/free_navigation_calculator.py`)

Create a new class for handling "Contract Navigation" (2.A3) and "Turnpoint Hunt" (2.A6).

**State Tracking:**
*   `visited_ids`: Set[str] (names/IDs of visited waypoints).
*   `expected_order`: List[str] (from `contestant.declared_configuration['waypoint_order']`).
*   `next_expected_index`: Int (0).

**Methods:**
*   `__init__(self, free_waypoints: list[Waypoint], declared_order: list[str], scorecard: Scorecard)`
*   `process_position(self, position) -> UpdateScoreMessage | None`:
    *   Iterate through all `free_waypoints` NOT in `visited_ids`.
    *   Check distance to waypoint center.
    *   If `distance < waypoint.radius` (or `width`):
#### A. `FreeWaypointCalculator`
*   **Responsibility:** Monitor proximity to a set of "free" waypoints.
*   **Logic:**
    *   On each position update, check distance to all unvisited free waypoints.
    *   If inside `inside_distance` and not previously visited:
        *   Mark as visited.
        *   **For Sequence Tasks (2.A3):**
            *   Check if `waypoint.name == expected_order[next_expected_index]`.
            *   If YES: Award points, increment `next_expected_index`. Emit Score.
            *   If NO: This implies an out-of-order hit. Depending on rules, either ignore or penalize. CIMA 2.A3 requires exact order.
        *   **For Hunt Tasks (2.A6):**
            *   Award `waypoint.score_value`. Emit Score.
        *   Record time.
        *   Validate order (if `contestant.declared_configuration.waypoint_order` is defined).
        *   Update Score.

### 3.3. Integration into `GatekeeperRoute` (`src/display/calculators/gatekeeper_route.py`)
#### B. `CircleCalculator`
*   **Responsibility:** Score the Circle task (2.A7).
*   **Logic:**
    *   **Phase 1 (Entry):** Detect crossing of Start Point (SP) and Center Marker (CM).
    *   **Phase 2 (Orbit):**
        *   After passing CM, track the flight path.
        *   Calculate distance from CM for every point.
        *   Maintain `min_radius` and `max_radius` observed.
        *   Check for altitude violations (±200ft).
        *   Check for leaving the valid radius range (200m - 750m).
    *   **Phase 3 (Exit):** Detect crossing of the entry line (X) after 180 degrees.
    *   **Scoring:** Apply formula `P = (Rmin/Rmax - 0.5) * 500`.

The `GatekeeperRoute` is the main orchestrator.
#### C. `SpeedSectionCalculator`
*   **Responsibility:** Score speed legs (2.A8, 3.A5, 3.B5).
*   **Logic:**
    *   Detect crossing of `Speed Start`.
    *   Detect crossing of `Speed End`.
    *   Calculate duration and speed.
    *   Apply penalties (e.g., min/max speed violation, or points based on speed relative to max).

**Changes:**
1.  **Initialization**:
    *   In `__init__`, detect if the route has Special Tasks (Circles, Free Points).
    *   Instantiate `CircleCalculator` and `FreeNavigationCalculator` and add them to a list of sub-calculators.
2.  **Processing Loop (`check_gates`)**:
    *   Call `sub_calculator.process_position(self.track[-1])` for each sub-calculator.
    *   Handle any `UpdateScoreMessage` returned by them and push to `self.score_processing_queue`.
#### D. `CIMAGatekeeper` (Optional Wrapper)
*   A subclass of `GatekeeperRoute` that initializes these sub-calculators based on the `NavigationTask` configuration.

## 4. API & Serializers
## 4. Task-Specific Implementation Details

### 4.1. `ContestantSerializer` (`src/display/serialisers.py`)
Mapping CIMA tasks to the new architecture:

Expose the new configuration field.
*   **2.A1 (Curve Nav with Time Est):**
    *   Use standard `GatekeeperRoute`.
    *   Use `Contestant.declared_configuration['leg_speeds']` for gate time calculation.
*   **2.A3 (Contract Nav):**
    *   Use `GatekeeperRoute` for SP, MP, FP.
    *   Use `FreeWaypointCalculator` for the "free" points.
    *   Input: Pilot declares order in frontend -> saved to `Contestant.declared_configuration`.
*   **2.A5 (Unknown Legs):**
    *   Enhance Route Editor to better support "Unknown Leg" segment types (visual cues).
    *   Calculator logic remains mostly standard `GatekeeperRoute` as the actual path is flown sequentially, just not known beforehand.
*   **2.A6 (Turnpoint Hunt) / 2.B1 (Split Square) / 2.B2 (Limited Fuel):**
    *   Use `FreeWaypointCalculator`.
    *   For 2.A6, the order is pilot-optimised.
    *   For 2.B1, the "square" part is sequential (Gatekeeper), the "optional marker" is Free.
*   **2.A7 (Circle):**
    *   Use `CircleCalculator`.
*   **2.B3 (Duration):**
    *   Simple `Gatekeeper` with just TO and LANDING.
    *   Score is `Landing Time - Takeoff Time`.

```python
class ContestantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contestant
        fields = [..., 'declared_configuration']
        read_only_fields = [..., 'declared_configuration'] # Or writeable depending on view permissions
```
## 5. Frontend & User Interface Changes

Create a specialized serializer `ContestantDeclarationSerializer` for the pilot input form:
```python
class ContestantDeclarationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contestant
        fields = ['declared_configuration']
    
    def validate_declared_configuration(self, value):
        # Validate schema (e.g. check all leg_speeds are numbers)
        return value
```
### 5.1. Contestant Dashboard

### 4.2. Views (`src/display/views_api.py`)
*   **Declared Speed Interface:** A table allowing the pilot/admin to enter a speed (Knots/Km/h) for each leg of the route.
*   **Waypoint Ordering Interface:** A drag-and-drop list to define the sequence of free waypoints (for Contract Nav).
*   **Synchronization:** These forms must save data to the `Contestant.declared_configuration` field via API.

Ensure the `ContestantViewSet` allows PATCH requests to `declared_configuration` for the authenticated user (if they are the pilot) or admin.
### 5.2. Live Map
*   **Circle Visualization:** Draw the circle min/max bounds and the target radius on the map.
*   **Free Waypoints:** Display them differently (e.g., distinct icon/color) to indicate they are not part of the sequential string line.
*   **Pilot's Planned Route:** If a pilot has a custom order, draw lines connecting the waypoints in *their* declared order when that pilot is selected.

### 5.3. Route Editor (React)

Modifications to `react_vite/src/features/route-editor/` to support creating CIMA task features.

#### A. Data Types (`react_vite/src/types.ts`)
Extend the core types to support new point attributes.

```typescript
export interface RoutePoint extends LatLng {
  // ... existing fields ...
  type: "sp" | "tp" | "secret" | "fp" |
        "circle_center" | "circle_entry" |
        "free_point" | "speed_start" | "speed_end";
  radius?: number; // In meters (for circle_center)
  score?: number;  // Points (for free_point)
  groupId?: string; // To link start/end or center/entry
}

export type Mode = "view" | "add_point" | "add_landing" | "add_takeoff" |
                   "add_observation" | "add_polygon" |
                   "add_circle" | "add_free_point";
```

#### B. Toolbar (`react_vite/src/features/route-editor/components/Toolbar.tsx`)
Add new tool buttons to the toolbar.

*   **Circle Tool:** Sets mode to `add_circle`. Icon: `Circle` (lucide-react).
*   **Free Point Tool:** Sets mode to `add_free_point`. Icon: `Flag` (lucide-react).

#### C. Point Editor (`react_vite/src/features/route-editor/components/EditPointView.tsx`)
Update the sidebar form to allow editing specific properties based on the selected point type.

*   **Type Dropdown:** Add options for "Circle Center", "Circle Entry", "Free Waypoint", "Speed Start", "Speed End".
*   **Conditional Inputs:**
    *   If `type === 'circle_center'`: Show input for **Radius (m)**.
    *   If `type === 'free_point'`: Show input for **Score Value**.
    *   If `type` is Speed/Circle related: Show/Edit **Group ID**.

#### D. Map Canvas (`react_vite/src/features/route-editor/components/MapCanvas.tsx`)
*   **Rendering:**
    *   Draw a dashed circle overlay for points with `type === 'circle_center'` using the `radius` property.
    *   Use distinct colors/icons for Free Points (e.g., Blue) vs Sequential Points (Green/Red).
*   **Interaction:**
    *   Handle `add_circle` click: Create a `circle_center` point. Optionally, next click creates `circle_entry`.
    *   Handle `add_free_point` click: Create a `free_point`.

## 6. Testing Strategy

1.  **Unit Tests (`src/display/tests/`)**:
    *   Test `CircleCalculator` with simulated position sequences (Enter -> Orbit perfect -> Exit, Enter -> Orbit bad radius -> Exit).
    *   Test `FreeNavigationCalculator` with correct and incorrect orders.
    *   Test `Contestant.calculate_missing_gate_times` with declared speeds.
2.  **Integration Tests**:
    *   Create a Route with a Circle. Run a simulated track through it via `GatekeeperRoute`. Verify final score.
1.  **Phase 1:** Model updates (`Waypoint`, `Contestant`, `Scorecard`).
2.  **Phase 2:** Route Editor updates to support creating Circle and Free waypoints.
3.  **Phase 3:** Backend logic for `FreeWaypointCalculator` and `Contestant` speed declarations.
4.  **Phase 4:** Backend logic for `CircleCalculator`.
5.  **Phase 5:** Frontend UI for declarations and Map updates.
6.  **Phase 6:** Integration testing with full CIMA task flows.