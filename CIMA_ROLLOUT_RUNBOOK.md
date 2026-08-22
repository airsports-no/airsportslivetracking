# CIMA Rollout Runbook

Merging `cima_hermes` into production: a four-stage rollout from
code-consolidated-but-dark to generally available, with the exact config and
access grants for each stage. One deploy carries you through all four
stages — Stages 2 and 3 are database grants, not redeploys. Only Stage 4
touches config again.

- Branch: `cima_hermes` → `main`
- Head at time of writing: `02da2a51`
- Full test suite: 881 passed

---

## Before you fly (pre-flight)

This branch carries 23 new migrations, most of them additive. Two are not:

**`0163_dedupe_scorelogentry_and_correct_totals` — irreversible.**
Deletes duplicate `ScoreLogEntry` rows created by a historical replay bug,
and adjusts `GateCumulativeScore` and `ContestantTrack.score` to match. It's
deliberate and well-documented — it must run before `0164` adds the unique
constraint those duplicates would violate — but it mutates historical
scoring data with no reverse migration.

- Take a full database backup immediately before running migrations.
- Capture the migration's stdout — it prints every contestant/gate it
  touches, as your audit trail.

**`0149_remove_task_limit_fields` — schema drop.**
Drops two columns outright. Not reversible by migrating backward once data
has been written against the new schema.

---

## How the gate actually works

Two settings control whether CIMA task types are visible and usable, and
one enforcement call now guards every path that can create a navigation
task:

| | |
|---|---|
| `GATE_CIMA_TASK_VISIBILITY` | Default `false`. When off, every user sees every task-type group — the entire gate is a no-op. Must be `true` for any of the below to matter. |
| `DEFAULT_FREE_TASK_TYPE_GROUPS` | Default `"legacy,cima"` — CIMA free for everyone even with the gate on. Set to `"legacy"` to require a grant. |
| `assert_can_add_navigation_task` | The save-time check. Previously only called from the Django wizards; now also enforced in all three DRF paths that create a `NavigationTask`, so a gated task type is blocked, not just UI-hidden. |

**Common trap:** `ACCESS_ENFORCEMENT_MODE` (`audit` / `enforce`) sounds like
it should govern this, but it doesn't — it only gates whether
contestant-count limits block contestant creation. The CIMA task-type check
never reads it and is always hard-enforced. Leave it at `audit`; it has no
bearing on CIMA lockdown either way.

---

## Stage 1 — Consolidate

**CIMA visible to no one.**

Ship the merged code with the feature dark. Behaviour-neutral for every
existing user — this is a consolidation deploy, not a feature launch.

### Config

```
GATE_CIMA_TASK_VISIBILITY=true
DEFAULT_FREE_TASK_TYPE_GROUPS=legacy
ACCESS_ENFORCEMENT_MODE=audit                 # unchanged
DEFAULT_FREE_CONTESTANT_LIMIT=<unset>         # unlimited, unchanged
```

Already committed in `helm/templates/configmap_other.yaml` — nothing
further to edit for this stage.

### Steps

1. **Back up the database.**
2. **Deploy the merged branch.**
3. **Run migrations.** Save the output of `0163` — it's your record of
   what it changed.
4. **Verify as a non-superuser.** Contest creation and the route-editor
   wizard must show no CIMA task types.
5. **Recalculate one existing legacy contestant.** Diff the score against
   its pre-deploy value — proves the scoring engine is untouched by the
   merge.
6. **Generate one flight-order PDF.** The merge brought in main's
   LaTeX→Typst rewrite of PDF generation — genuinely new code in
   production. Eyeball the output for a legacy contestant.
7. **Confirm no contestant-limit messaging appears.** Audit mode +
   unlimited free tier means nothing should surface here.

---

## Stage 2 — You test

**CIMA visible to you only.**

No config change — Stage 1's deploy already covers this. Grant your own
account access and go test the CIMA task types directly.

### Grant yourself access

If your account is a superuser, you already have every task-type group —
`get_user_granted_task_type_groups()` returns everything for superusers
before any other check runs. Test as a **non-superuser account too**, or
you're never actually exercising the gate you just locked down.

1. Django admin → **Display → User entitlement grants → Add**.
2. Set the fields: `User` = your test account. `Kind` = Task-type group.
   `Value` = `cima` for every CIMA subtype, or `cima:circle` to scope to
   one. Set `Expires at` for hygiene; toggle `Is active` off any time to
   revoke instantly — no deploy required.
3. Save. `granted_by` is set automatically.

### What to test

The riskiest area of this branch: the flight-order generator's CIMA
declaration-aware seam, which had to be rebuilt during the merge (main's
rewrite had silently dropped it).

1. Create one contest per CIMA subtype you care about.
2. Check the map, flight order, and gate-times table — each should reflect
   a contestant's *declared* route, not the shared route backbone.
3. Run a track through the scoring engine end to end.

---

## Stage 3 — Testers

**CIMA visible to named testers.**

Same mechanism as Stage 2, repeated per tester. Still no config change.

1. Add a User entitlement grant per tester, with an `Expires at` date —
   this is a beta, not a standing entitlement.
2. Confirm the split with two accounts: one granted tester sees CIMA task
   types; one ungranted colleague does not.
3. If any tester drives the API directly (not the web UI), confirm a
   gated request is rejected — `assert_can_add_navigation_task` now runs
   on every create path, so it should be.

---

## Stage 4 — General release

**CIMA visible to everyone.**

The one stage that does need a config change. Either is sufficient on its
own:

```
GATE_CIMA_TASK_VISIBILITY=false
```
or
```
DEFAULT_FREE_TASK_TYPE_GROUPS=legacy,cima
```

Existing per-user/per-club grants keep working unchanged either way — they
simply stop being the only route to access.

---

## Reference

### Config by stage

| Stage | `GATE_CIMA_TASK_VISIBILITY` | `DEFAULT_FREE_TASK_TYPE_GROUPS` | Who has CIMA |
|---|---|---|---|
| 1 — Consolidate | true | legacy | Superusers only |
| 2 — You test | true | legacy | You + superusers (grant) |
| 3 — Testers | true | legacy | + named testers (grants) |
| 4 — General release | false | legacy, cima | Everyone |

### Where this lives in code

| | |
|---|---|
| `settings.py` | Defaults for all four settings above, plus `DEFAULT_FREE_CONTESTANT_LIMIT` and `ACCESS_ENFORCEMENT_MODE`. |
| `task_type_visibility.py` | `get_visible_task_type_groups_for_user()` — what the UI shows. Never reads `ACCESS_ENFORCEMENT_MODE`. |
| `capacity_enforcement.py` | `assert_can_add_navigation_task()` — the save-time block. Unconditional; not gated by enforcement mode. |
| `UserEntitlementGrant` | `display/models/access_control.py` — per-user beta grants, kind `task_type_group`, value `cima` or `cima:<subtype>`. |
| `configmap_other.yaml` | `helm/templates/` — production env vars; Stage 1's two lines are already committed here. |

### New migrations on this branch (23)

Full range `0143`–`0165`. Flagged above: `0149` (schema drop), `0163`
(data mutation, must precede `0164`'s unique constraint).

### Branch history

| Commit | What it fixed |
|---|---|
| `ef12cc62` | Hung `PokerCalculator` unit test causing the full suite to OOM |
| `36399f02` | Test suite off the network and out of Redis (2132s → 946s) |
| `92c197e9` | Geodesic solve per leg per position in the scoring hot path (→ 837s) |
| `131c4f80` | Flight-order config doing up to 114 HTTP requests per instantiation (→ 770s) |
| `49fb73be` | Merged main, including its LaTeX→Typst flight-order rewrite |
| `fd019c92` | Restored the CIMA declaration-aware waypoint seam the Typst rewrite dropped |
| `02da2a51` | API-level CIMA gate enforcement + this rollout's production config |
