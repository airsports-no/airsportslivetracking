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

#### Rule D: Upfront Task Capacity Gate ($N$)

A tier or token grants a capacity limit of $N$ unique guest pilots. This single parameter $N$ enforces two concurrent ceilings:

1. **Upfront Task Reservation Limit:** A single `NavigationTask` may reserve at most $N$ non-owner primary pilots at any time, counting:
   - historic started guest pilots already stamped on that task, plus
   - currently registered/scheduled guest pilots on that task whose primary pilot has not already been stamped for the same task.
2. **Contest Unique Limit:** An overarching `Contest` can have at most $N$ unique guest pilots across all of its tasks combined.
3. **No Over-subscription:** Organizers cannot add new non-owner contestants to a task once all guest pilot slots for that task are reserved, unless they are reusing an already-counted primary pilot.

#### Rule E: Slot Lifecycle, Historical Ledgering & Re-creation

* **Upfront Reservation:** Adding a contestant to a task reserves 1 guest pilot slot for that task unless the contestant reuses a primary pilot who is already counted for the same task.
* **Permanent Stamp (Calculator Start):** Once the scoring calculator actually starts / initializes processing for a contestant's task flight, that contestant's primary pilot becomes permanently stamped in the task’s historical usage ledger.
* **Deletion Before Start:** If a contestant is deleted from a task before their calculator starts, their reservation is released back into the task's available capacity pool.
* **Deletion After Start:** If a contestant is deleted after their calculator has started, their slot remains permanently burned as a historic pilot slot and continues to count toward the task limit $N$.
* **Primary Pilot Identity (`Person`):** Billable slots are bound directly to the **Primary Pilot `Person` record** (`team.crew.member1`), rather than the transient `Team` object ID.
* **Same-Pilot Re-creation / Re-assignment (`Person`):** If a deleted historic contestant is re-added or updated using the same Primary Pilot `Person` (even with a new team/aircraft ID), the system re-links them to their existing stamped slot at zero additional quota cost.
* **Team Modifications (Aircraft / Copilot Swap):** If a team's composition changes without changing the Primary Pilot `Person`, the existing reservation or historic slot is reused.
* **Primary Pilot Replacement:** If the Primary Pilot `Person` changes, it is treated as a distinct contestant entry. The original pilot's started slot remains permanently burned once their calculator has started, and the new pilot consumes an additional slot.
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
