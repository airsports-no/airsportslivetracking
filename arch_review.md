 Architecture Overview: Position Tracking & Scoring Pipeline

  The tracking architecture is a robust, decoupled, multi-stage pipeline designed to handle high-frequency telemetry, isolate computational loads, and seamlessly support
  concurrent overlapping contestants sharing the same tracking device.


  Stage 1: Ingestion (src/position_processor.py)
   1. WebSocket Connection: Connects directly to the Traccar API via WebSocket.
   2. Buffering: Deserializes raw JSON streams and immediately places them into a fast, in-memory multiprocessing.Queue (processing_queue).
   3. Resiliency: Implements aggressive connection checking (check_connection), toggling Kubernetes liveness probes if the connection goes stale to trigger automatic pod
      restarts.


  Stage 2: Dispatch & Routing (src/position_processor_process.py)
   1. Device-to-Contestant Mapping: The initial_processor consumes the processing_queue. It relies on map_positions_to_contestants to map the Traccar deviceId to an internal
      tracker string, then uses cached_find_contestant to map that device to one or more active Contestants.
   2. Duplicate Filtering: Utilizes a combination of Redis (last_seen_key) and timestamp evaluation to quietly drop duplicate or extremely old (14+ hours) coordinates.
   3. Process/Job Invocation: Calls add_positions_to_calculator. This creates a dedicated RedisQueue for the contestant and invokes either a local Python Process or a Kubernetes
      Job (JobCreator). The position is pushed to the contestant's specific RedisQueue.


  Stage 3: Processing & Scoring (src/display/calculators/contestant_processor.py)
   1. Historical Rehydration: On startup, the enqueue_positions_thread explicitly fetches historical data via HTTP from Traccar from the tracker_start_time up to now. This
      ensures crash-resiliency—if a Kubernetes job dies and restarts, it perfectly recovers the flight path.
   2. Anti-Cheat Buffering: Positions are pushed into a TimedQueue, which artificially delays their release to the scoring engine based on the task's calculation_delay_minutes.
   3. Gap Filling (The Hot Path): In the main run() loop, popped positions are compared to the previous_position. If a gap of >6 seconds is detected, a synchronous HTTP call to
      Traccar is made to fetch the missing data (check_for_buffered_data_if_necessary).
   4. Interpolation: Positions are passed to interpolate_track, filling 1-second gaps via linear interpolation using the newly unified AEQD Projector.
   5. Scoring: Every interpolated and raw position is fed into the Gatekeeper for geometric evaluation and score generation.

  ---

  Analysis: Handling Overlapping Contestants

  The implementation for handling overlapping contestants (multiple pilots using the same tracker across different tasks simultaneously) is handled exceptionally well at the
  architectural level:


   1. Fan-out Dispatch: cached_find_contestant returns a list of valid tuples [(Contestant1, is_sim), (Contestant2, is_sim)]. The dispatcher iterates through this list,
      appending the exact same raw coordinate to both contestants' RedisQueues.
   2. Complete Isolation: Because each contestant has their own RedisQueue and their own ContestantProcessor (running in separate processes/pods), the computational
      heavy-lifting of scoring is perfectly isolated.
   3. Independent Lifecycles: Overlapping flights manage their own timeouts, late-starts, and delays independently without interfering with the other active task.

  ---


  Improvement Suggestions

  While the architecture is highly scalable and resilient, there are several areas where performance and reliability can be improved.


  High Priority: Relocate Synchronous Gap-Filling
  Issue: Inside ContestantProcessor.run(), the check_for_buffered_data_if_necessary function performs a synchronous HTTP request (self.traccar.get_positions_for_device_id) to
  the Traccar API if a data gap > 6 seconds is detected. Because this happens in the main processing loop, a slow response from Traccar will block the scoring engine, delay
  WebSocket telemetry updates to the frontend, and block the evaluation of termination conditions.
  Suggestion:
  Move gap detection and filling into the enqueue_positions_thread. The background thread should identify gaps as data comes in from the RedisQueue, make the HTTP call to
  Traccar to fetch missing points, and then push the complete, contiguous block of points into the TimedQueue. This keeps the main run() loop completely CPU-bound and
  lightning-fast.


  Medium Priority: Redundant HTTP Calls for Overlapping Contestants
  Issue: Because the pipeline fans out early (in position_processor_process.py), if a tracker is shared by 3 active contestants and goes offline for 10 seconds, all 3 isolated
  ContestantProcessors will independently detect the gap and simultaneously make the exact same HTTP request to Traccar to fetch the missing data.
  Suggestion:
  Consider moving the check_for_buffered_data_if_necessary logic upstream into the initial_processor (position_processor_process.py). The central dispatcher could identify gaps,
  fetch the missing data from Traccar once, and then fan-out the contiguous list of coordinates to the RedisQueues. (Note: The initial historic fetch on calculator startup would
  still need to remain in the contestant processor to handle crash recovery).


  Medium Priority: In-Memory Cache Staleness (cached_find_contestant)
  Issue: contestant_cache in position_processor_process.py is a local Python dictionary. It determines cache validity using a TTL (valid_to = min(60s, finish_time - now)). If a
  user manually terminates a contestant via the frontend, the initial_processor will continue routing positions to that contestant's RedisQueue for up to 60 seconds until the
  local cache expires.
  Suggestion:
  Use the central Django cache (Redis) for routing resolution instead of a local dictionary. When a contestant is manually terminated (or finished), invalidate their specific
  tracker routing key in Redis. This allows the dispatcher to react instantly to manual overrides.


  Low Priority: RedisQueue Polling Mechanics
  Issue: In ContestantProcessor.enqueue_positions_thread, the code catches RedisEmpty and uses time.sleep(0.5) if no data is found.
  Suggestion:
  Ensure the underlying RedisQueue.pop() uses Redis's blocking BLPOP command rather than actively polling and sleeping. BLPOP blocks at the Redis level with zero CPU overhead
  and responds with microsecond latency when data arrives.

Computational Efficiency (Calculation Side)
   1. Batch Score Logging: Currently, ScoreLogEntry and TrackAnnotation are saved individually. During recalculations or dense penalty zones, this generates high DB load. These
      should be batched similarly to how ContestantReceivedPosition objects are saved in groups of 100.
   2. Atomic Increments: update_score_from_thread refreshes the full ContestantTrack object from the database for every update. Using Django's F() expressions for the score
      field would allow atomic increments without the overhead of a full model refresh and save.
   3. Redis Blocking Pops: The loop in run() occasionally peeks at Redis or sleeps. Transitioning to blocking pops (BLPOP) or using Redis keyspace notifications for termination
      requests would reduce CPU idling and improve responsiveness.


  User Experience & Management Efficiency
   1. Unified Task Scaffolding: Currently, creating a contest, route, and task is a multi-step process. A "Task Creation Wizard" that accepts a KML/GPX upload and generates the
      Task and Route in a single step would significantly reduce management friction.
   2. Bulk Contestant Import/Cloning:
       * Implement CSV/Excel import for team registrations.
       * Add a "Clone Contestants" feature to allow managers to copy a full roster from one Navigation Task to another within the same Contest (e.g., Task 1 -> Task 2).
   3. Aeroplane Profiles: Create pre-defined profiles for common aircraft (e.g., Cessna 172, Piper Warrior) that store default airspeeds. This would allow managers to select a
      profile instead of manually typing airspeed for every contestant.
   4. Integrated Scheduling: The Scheduling Assistant is powerful but feels disconnected. Allowing the assistant to directly populate contestant takeoff times within the Task
      Detail view would eliminate the need for manual copy-pasting of times.

---

Here is a comprehensive architectural review of the application, focusing on computational efficiency within the scoring engine and the management UX/UI for creating and
  configuring competition structures.

  ---

  1. Architectural Overview

  The application is structured into two primary domains that communicate asynchronously:


  A. The Asynchronous Scoring Engine (Calculation Side)
   * Ingestion (position_processor.py): A persistent WebSocket connection to Traccar ingests real-time position data and pushes it into an in-memory queue.
   * Multiplexing (position_processor_process.py): The initial_processor reads from the queue, queries the database (via a cache) to resolve deviceIds to active Contestants, and
     pushes the data to individual, contestant-specific RedisQueues.
   * Distributed Processing (ContestantProcessor): Each active contestant gets a dedicated calculator process (locally or as an isolated Kubernetes job). This isolates failures
     and allows for horizontal scaling.
   * Scoring Logic (Gatekeeper & Calculators): The processor orchestrates various calculators (e.g., AnrCorridorCalculator, BacktrackingAndProcedureTurnsCalculator). Points of
     interest (gates, zones, polygons) are validated against interpolated 1-second interval track arrays.
   * Score Delegation: Mathematical evaluations emit UpdateScoreMessages pushed into an internal Queue. A background score_updater_thread processes these, saving ScoreLogEntry
     and TrackAnnotation objects to PostgreSQL, decoupling heavy database I/O from the live trajectory calculation loop.


  B. The Django Management Portal (User Experience Side)
   * Relational Hierarchy: Contest (the event) -> NavigationTask (a single route/competition) -> Contestant (an instance of a Team flying the task).
   * Form Wizards (views_wizards.py): The creation of complex entities (NavigationTask, Team) is handled via multi-step session wizards.
   * Real-time UI: Templates utilize WebSocket feeds (via Daphne/Channels) to reflect live score updates, track states, and online/offline tracking indicators.

  ---

  2. Computational Efficiency (Calculation Side)

  The scoring engine processes a tremendous amount of spatial data. While the recent Projector (AEQD) implementations bypassed the expensive Haversine calculations, several
  bottlenecks remain.


  Current Bottlenecks & Weaknesses:
   1. High Database I/O under Penalty Conditions: When a contestant enters a continuous penalty state (e.g., Backtracking or Outside Corridor), the score_updater_thread creates
      a new TrackAnnotation and ScoreLogEntry almost every second.
   2. Threaded Waiting (timed_queue.py): The enqueue_positions_thread and main run() loop utilize standard sleep/timeout intervals when pulling from Redis. This results in idle
      CPU cycling.
   3. Contestant Polling: The engine frequently queries the DB to check if the contestant's finished_by_time was changed manually by the frontend.


  Improvement Suggestions:
   * Batch Database Inserts for Logs: Accumulate ScoreLogEntry and TrackAnnotation objects in memory within the score_updater_thread and use bulk_create (saving them in chunks
     of 50-100) exactly like the ContestantReceivedPosition logic currently does.
   [x] Atomic Updates: In update_score_from_thread, the entire ContestantTrack object is retrieved and saved just to increment the score. Switch to Django's F() expressions
     (ContestantTrack.objects.filter(pk=...).update(score=F('score') + new_points)) to avoid race conditions and reduce DB overhead.
   * Redis Blocking Pops / PubSub: Switch from continuous polling to Redis BLPOP for incoming positions, and use a Redis PubSub channel to send "Terminate" or "Update Time"
     signals from the Django web backend directly to the active ContestantProcessor, entirely removing the need for the processor to constantly re-query the database for
     configuration changes.

  ---

  3. Usability & User Experience (Management Side)


  The management workflow is overly segmented. While Form Wizards are great for edge-case validation, they create high friction for standard, repetitive operations.


  Current Bottlenecks & Weaknesses:
   1. Cumbersome Wizards: Registering a team (RegisterTeamWizard) requires up to 7 isolated steps (Pilot search, Pilot create, Copilot search, Copilot create, Aeroplane, Club,
      Tracking). Creating a new navigation task (NewNavigationTaskWizard) takes 6 steps.
   2. Repetitive Data Entry: If a manager runs a 5-day contest with 5 tasks, they must manually assign the exact same roster of 20 teams to each task, configuring their trackers
      every time.
   3. Scattered Settings: Editing a contestant requires diving into a detail page, while bulk-modifying their takeoff times requires switching to a separate "Scheduling
      Assistant" view.

  Improvement Suggestions:


   * Single-Page Registration (SPA/Dynamic Form):
      Replace the 7-step RegisterTeamWizard with a single, dynamic form (potentially using Alpine.js, HTMX, or your existing React/Vite stack). A user should be able to select
  an existing Pilot from a dropdown (which auto-populates the fields), type an aircraft registration, assign a tracker ID, and hit "Save" on a single screen.


   * "Clone Task Roster" Feature:
      Add a button on the NavigationTask detail page called "Import Contestants from Previous Task". This would allow a manager to duplicate the entire active roster (along with
  their specific aircraft and assigned tracker IDs) from Task 1 into Task 2 instantly.


   * Task & Route Unified Upload:
      Currently, users must upload an EditableRoute via a KML file in one part of the UI, then attach it to a NavigationTask via a wizard. Allow managers to create a
  NavigationTask by dragging and dropping a KML file directly onto the "Create Task" page. The backend should silently create the EditableRoute and link it behind the scenes.


   * Inline Editing (Data Grids):
      The desktop view of the contestants table (navigationtask_detail.html) should be transformed into an inline-editable grid. Managers should be able to click on a "Takeoff
  Time" or "Airspeed" cell, type a new number, and press Enter to save it via an API call, rather than navigating away to a separate ContestantUpdateView.


  ---

  This design addresses the friction of the current 7-step wizard by moving to a "Search-First, Create-if-Missing" architecture. It leverages the existing React/Vite stack and
  adds new specialized API endpoints to handle nested object creation.

  ---

  1. Frontend Architecture (React/Vite)

  The frontend will be built as a standalone module within the react_vite directory.


  Key UI Components:
   * TeamRegistrationForm.tsx: The main container managing the overall form state and submission.
   * CreatableEntitySelect.tsx: A wrapper around react-select/creatable. This is the core of the UX. It allows users to search for existing entities (Pilot, Plane, Club) and
     provides a "Create New" option if no match is found.
   * NestedPersonForm.tsx: A conditional sub-form that appears when a user chooses to create a new Pilot or Copilot (fields: First Name, Last Name, Email, Phone).


  Frontend State Management:
  The form state would be a flat object, where fields can either be an ID (for existing entities) or a nested object (for new ones):


   1 interface RegistrationState {
   2   pilot: string | NewPerson;    // UUID/ID or { first_name, last_name, ... }
   3   copilot: string | NewPerson | null;
   4   aeroplane: string | NewPlane; // ID or { registration }
   5   club: string | NewClub;
   6   tracker_id: string;
   7   air_speed: number;
   8 }


  UX Flow:
   1. Pilot Search: User types "Smi...". The dropdown lists "John Smith".
   2. Selection: User selects John. The Pilot section collapses to a "John Smith (Selected)" badge with an "Edit/Change" button.
   3. Creation: If John isn't there, the user clicks "Create New 'Smi...'". A small inline form appears to collect John's email and phone.


  ---

  2. Backend Architecture (Django REST Framework)


  To support this SPA, the backend needs to move from a multi-view session approach to a single atomic POST endpoint.


  Existing endpoints, similar to:
   1. Search Endpoints (GET):
       * /api/v1/search/persons/?q=...
       * /api/v1/search/aeroplanes/?q=...
       * /api/v1/search/clubs/?q=...
       * Implementation: Use django-filter or simple icontains on relevant fields.


   2. Unified Registration Endpoint (POST):
       * /api/v1/navigation-tasks/<id>/register-team/
       * Implementation: A custom APIView that uses a Nested Serializer.


  The Serializer Logic:
  The Serializer will use the to_internal_value or create method to handle the "ID or Object" logic:


    1 class TeamRegistrationSerializer(serializers.Serializer):
    2     pilot_data = PersonSerializer(required=False)
    3     pilot_id = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all(), required=False)
    4     # ... same for copilot, aeroplane, club ...
    5
    6     def create(self, validated_data):
    7         with transaction.atomic():
    8             # 1. Resolve or Create Pilot
    9             pilot = validated_data.get('pilot_id') or Person.objects.create(**validated_data['pilot_data'])
   10             # 2. Resolve or Create Aeroplane
   11             plane = validated_data.get('aeroplane_id') or Aeroplane.objects.create(...)
   12             # 3. Create Crew and Team
   13             crew = Crew.objects.create(member1=pilot, ...)
   14             team = Team.objects.create(crew=crew, aeroplane=plane, ...)
   15             # 4. Create Contestant
   16             contestant = Contestant.objects.create(team=team, navigation_task=self.context['task'], ...)
   17             return contestant

  ---


  3. Key Usability Gains


   1. Zero Navigation Latency: No page reloads between steps. All validation errors (e.g., "This plane is already registered in this task") appear instantly.
   2. Intelligent Defaults: When a user selects an existing Team (the plane + pilot combo), the system should offer to auto-fill the rest of the form based on their last task
      registration.
   3. Reduced Database Friction: Currently, the wizard creates partial objects in the database or stores them in the session. This SPA approach ensures that either everything is
      created (the pilot, the plane, the team, and the contestant) or nothing is, preventing "orphaned" pilots or teams.
   4. Keyboard-Driven Entry: A power user can tab through the fields, using search-as-you-type, and register a team in under 15 seconds.


  Implementation Strategy:
   1. API First: Develop the register-team POST endpoint and verify the three search GET endpoints.
   2. Scaffold Form: Create the basic React form using react-select.
   3. Refine Logic: Add the "Clone from previous contest" logic to the search results.
   4. The "Big Switch": Replace the "Add new team" button in the Django detail view with a link to this new React page.