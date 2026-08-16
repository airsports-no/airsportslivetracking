## Air Sports Live Tracking: Tier, Token & Contestant Business Logic

### 1. Core Philosophy & Value Model

* **Event Administration & Content Creation are Free; Task Execution Consumes Quota:** Registering teams, creating contests, building tasks, configuring routes, and uploading custom charts carry no financial cost. Paywalls are triggered exclusively when non-owner pilots participate in live navigation tasks.
* **Meter Unique Human Pilots, Not Task Submissions:** Quotas measure unique primary pilots (`Person`) participating in a contest, rather than the total number of task submissions or map uploads.

---

### Two purchase mechanisms, by design

Paid access is modeled two different ways on purpose, matching the two real ways
someone actually pays today (there is no payment processor integrated - both are
fulfilled manually by an operator):

* **`TokenType` / `UserTokenGrant` / `ContestTokenAssignment`** — a user emails to
  buy a token packet. It's owned by the *user*, and they assign single uses of it
  to whichever contest they organize.
* **`AccessGrant`** — a club buys a standing annual pass. It's owned by the *club*,
  and applies automatically to every contest that club organizes (or, for a
  single event, an operator grants it directly against one contest).

Both funnel into the same `resolve_contest_access()` waterfall, so callers never
need to know which mechanism is backing a given contest's access. This is not
redundancy to be cleaned up - see the docstrings on `AccessGrant` and `TokenType`
(`display/models/access_control.py`) for the full reasoning. A third, separate
mechanism, `UserEntitlementGrant`, exists purely for giving one specific user
something directly with no club/contest/payment involved (see §4 below) - it's
the "beta tester" case, not a purchase.

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

---

### 4. CIMA Task-Type Rollout (Beta → Paywall)

New CIMA catalogue task types (`display.utilities.cima_task_type_definitions`) are gated
as a single task-type group (`"cima"`), separate from ordinary contestant-quota billing.
Visibility/usage is resolved per-user by `display.services.task_type_visibility` and
enforced per-contest-add by `display.services.capacity_enforcement.assert_can_add_navigation_task`,
which unions the acting user's visible groups with the target contest's resolved groups —
so a user's own grant is usable in any contest they organize, not only ones organized
under a specific club.

**Turning gating on:** set env `GATE_CIMA_TASK_VISIBILITY=true` and
`DEFAULT_FREE_TASK_TYPE_GROUPS=legacy` (dropping `cima` from the free defaults — the
out-of-the-box default is `legacy,cima`, i.e. fully open). Until both are set, everyone
sees and can add CIMA tasks.

**Task-type group granularity:** every CIMA subtype belongs to the coarse `"cima"`
group *and* its own namespaced fine group, e.g. `"cima:circle"`
(`display.utilities.task_type_group_definitions.get_fine_task_type_group`).
Enforcement accepts either — a grant using the coarse `"cima"` string (the only
form that existed before fine-grained grants) still unlocks every CIMA subtype
unchanged; a grant using a namespaced `"cima:<subtype>"` string unlocks only that
one subtype. Nothing about existing `AccessGrant`/`TokenType` rows needs to
change to keep working.

**Beta rollout for one specific user (no code, admin-only):** use
`UserEntitlementGrant` (Django admin) — this is the "give this person direct
access, no club/contest/payment involved" mechanism (see the "Two purchase
mechanisms" note above; this is a third, separate mechanism from both of them).
1. Add a `UserEntitlementGrant` with `user=<the beta tester>`,
   `kind=task_type_group`, `value="cima"` (all CIMA subtypes) or
   `value="cima:circle"` (just Circle, for example).
2. Optionally set `expires_at` to auto-expire the beta grant, or leave it blank
   for an indefinite grant; `is_active=False` revokes it immediately without
   deleting the record.
3. The grant applies in *any* contest that user organizes — it's tied to the
   user, not a club or contest.

**Beta rollout for a whole cohort (no code, admin-only):** the club-based
approach from before is still valid for granting a *group* of people access via
one club, rather than one `UserEntitlementGrant` per person:
1. Create a club to represent the beta cohort (e.g. "Air Sports Live Tracking Beta").
2. Create a club-scoped `AccessGrant` (`status=ACTIVE`, `task_type_groups=["cima"]`,
   or `["cima:circle"]` to scope the whole cohort to one subtype) for that club.
3. Add each beta tester as a `ClubManagerMembership` (role `manager` or `owner`) on that
   club. Plain club membership does **not** grant visibility — only managers count.
4. Beta testers can then see and add CIMA tasks in *any* contest they organize (their own
   club or the beta club), not only contests organized under the beta club itself.

**Paywall rollout (later):** create a `TokenType` with `task_type_groups=["cima"]`
(or a namespaced subset) and sell/assign it via the existing `UserTokenGrant` /
`ContestTokenAssignment` flow — the same visibility and enforcement paths already
honor token grants, no further code changes needed.
