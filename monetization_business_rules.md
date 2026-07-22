## Air Sports Live Tracking: Tier, Token & Contestant Business Logic

### 1. Core Philosophy & Value Model

* **Event Administration & Content Creation are Free; Task Execution Consumes Quota:** Registering teams, creating contests, building tasks, configuring routes, and uploading custom charts carry no financial cost. Paywalls are triggered exclusively when non-owner pilots participate in live navigation tasks.
* **Meter Unique Human Pilots, Not Task Submissions:** Quotas measure unique primary pilots (`Person`) participating in a contest, rather than the total number of task submissions or map uploads.

---

### 2. Primary Business Rules

#### Rule A: The Free Contest Owner Exception (`Owner Exempt`)

* The `Contest Owner` (creator) **never** consumes a billable contestant slot under any circumstances.
* The owner can build tasks, upload custom charts, run the contestant scheduling engine, and record solo test or pace flights infinitely across all tiers—including the Free Tier—at zero cost.
* The baseline **Free / Sandbox Tier** is defined strictly as **Owner + 0 Guest Pilots**.

#### Rule B: Ungated Team Registration

* Creating a `ContestTeam` or adding teams to an overarching `Contest` roster is **unlimited and ungated**.
* Organizers can collect pre-registrations with no cap weeks before an event without triggering a paywall or consuming token quota.

#### Rule C: Custom Maps & Charts (`Free & Ungated`)

* Uploading custom geo-referenced maps and competition overlays is **unlimited and free across all tiers** (including Free / Sandbox).
* **Upload Constraint:** Enforce a maximum file size of **100 MB per map file** (no hard limit on the total number of maps uploaded per contest/task).

#### Rule D: Dual-Ceiling Capacity Gates ($N$)

A tier or token grants a capacity limit of $N$ unique guest pilots. This single parameter $N$ enforces two concurrent ceilings:

1. **Task Simultaneous/Historical Limit:** A single `NavigationTask` can have at most $N$ non-owner contestants who have started (including all historic contestants recorded on the task ledger).
2. **Contest Unique Limit:** An overarching `Contest` can have at most $N$ unique guest pilots across all of its tasks combined.

#### Rule E: Quota Consumption, Historical Ledgering & Re-creation

* **Trigger Point (Calculator Start):** Adding a team to a task or pre-scheduling them does **not** consume a billable slot. A team claims a slot **only when the scoring calculator actually starts / initializes processing** for that contestant's task flight.
* **Irreversible Slot Usage & Historic Counting:** Once the calculator has started for a contestant in a task, that contestant's slot is permanently stamped in the task’s usage ledger as a historic contestant. Even if the contestant is later deleted or removed from the UI/task, **the consumed slot remains permanently burned and counts toward the task's historic total**.
* **Primary Pilot Identity (`Person`):** Billable slots are bound directly to the **Primary Pilot `Person` record** (`team.crew.member1`), rather than the transient `Team` object ID.
* **Team Modifications (Aircraft / Copilot Swap):** If a team's composition changes (e.g., swapping the copilot or changing the aircraft tail number), resulting in a new `Team` ID, the system evaluates slot usage via the Primary Pilot `Person`. As long as that `Person` matches an existing stamped ledger entry for that task/contest, re-creating or updating the contestant with the new `Team` ID **reuses the existing consumed slot** at zero additional cost.
* **Primary Pilot Replacement:** If the Primary Pilot `Person` changes, it is treated as a distinct contestant entry. The original pilot's slot remains permanently burned once their calculator has started, and the new pilot consumes an additional slot.
* **Multi-Task Recycling Across Contest:** Once a unique primary pilot `Person` is stamped on the contest-level usage ledger, they can participate in Task 2, Task 3, Task 4, etc., within that same contest at **zero additional contest-level quota cost**.
* *Example:* If 20 unique pilots start Task 1, and the *exact same* 20 pilots start Task 2, total contest-level quota consumed is **20 slots** (not 40). If 20 pilots start Task 1 and 20 *different* pilots start Task 2, total contest-level quota consumed is **40 slots**.

#### Rule F: No Task Creation Gating

* **Task creation is unlimited across all tiers.** Hard-capping the number of tasks inside a contest is unnecessary because metering unique pilots naturally bounds system compute load.
* Organizers are free to create, modify, or replace as many `NavigationTask` objects as weather or competition logistics demand, provided the contest remains within its validity time window.

#### Rule G: Token Validity Windows & Archive Locks

To prevent a single event token from being used to host a year-long league across dozens of tasks, tokens carry a defined **Time-to-Live (TTL)**:

* **Single Event Tokens (Standard Passes):** Valid for **14 Days** from activation/first flight. All tasks created within this 14-day window are covered under the single token.
* **Annual Club Passes:** Valid for **365 Days**. Specifically required for year-long cups, seasonal leagues, or weekly club practice tasks.
* **Archive Mode:** Once the validity window expires, existing task results, flight logs, leaderboards, and map visualizations remain **100% viewable forever (read-only)**. Adding new tasks or launching new live track sessions under that contest is blocked until a new token or annual pass is applied.

---

### 3. Tier & Pass Structure Summary

All paid passes include **Unlimited Navigation Tasks**, **Unlimited Custom Maps (≤100 MB each)**, and **Free Contest Owner Flights**.

* **Free / Sandbox:** **0 Guest Pilots** (Solo practice, task creation, custom map uploads, route building, pace flights forever).
* **Personal Pro / Micro:** **5 Unique Guest Pilots** (14-day window; ideal for instructor training and small practice duels).
* **Medium / Club Event Pass:** **15 Unique Guest Pilots** (14-day window; standard local club championships and rallies).
* **Large / Regional & National Pass:** **30 Unique Guest Pilots** (14-day window; regional qualifiers and national championships).
* **Annual Club Pass:** **Up to 15 or 30 Unique Guest Pilots** (365-day window; unlimited year-round tasks for seasonal club cups).
* **Unlimited (Elite):** **Unlimited Guest Pilots** (Custom SLA window; major international events like World Championships).
