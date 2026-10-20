---
layout: ../../layouts/DocsLayout.astro
title: "Series: Cups and Championships over Several Contests"
---

# Series: Cups and Championships over Several Contests

A **series** ranks the teams of several contests together. Use it for a cup, a league or a national championship that is held as a number of separate events: each event is its own contest, and the series adds up how each team did in all of them. The contests are called the **legs** of the series.

---

## When should I use a series?

| Situation | What to do |
| :--- | :--- |
| A national cup with four events at four airfields, run by different clubs | One contest per event, and one series that ranks them. |
| A club league where a pilot's best results over the season count | One contest per round, one series with *only the best N legs count*. |
| One event over a weekend, with several tasks | You do not need a series. Make **one contest** with several navigation tasks; the contest results add the tasks up. |

A series does not replace the contests. Each contest keeps its own tasks, results and visibility. The series only reads the final result of each contest and combines them.

## How the ranking works

1. **Each leg is ranked on its own**, by the contest's result. The best team has place 1. Teams with the same score share a place (1, 2, 2, 4).
2. **The places are combined**. There are two ways to score, chosen in the series settings:
   - **Add up the places, lowest wins** (the default). A team that was 1st, 3rd and 2nd has 6; the lowest total wins.
   - **Points for each place, highest wins.** The settings hold a table of points for first, second, third… place (the default is 25, 18, 15, 12, 10, 8, 6, 4, 2, 1). The highest total wins.
3. **A leg a team did not take part in** counts as one place worse than the last team in that leg (the number of teams plus one). Flying fewer legs therefore does not pay. With a points table a missing leg gives no points.
4. **Weight.** Each leg has a weight, 1 by default. Give the final a weight of 2 and its places count double.
5. **Only the best N legs count** (optional). With a season of eight rounds you can let only the best five count; the others are shown but left out of the total.
6. **A tie** is broken by the number of first places, then second places, and so on. Teams still level share the rank.

Because only the **places** are added up, the legs can be scored in different ways: a precision task where the lowest penalty wins and a race where the most points win can be in the same series.

### Who is ranked

By default the **pilot** is ranked: the same pilot in two contests is the same entrant, whichever navigator or aeroplane they had. If your cup is for fixed crews, choose **The crew** instead; then it must be the same pilot and navigator (in either seat).

People are recognized by their ASLT profile, so a pilot who is registered with two different profiles will appear twice. Ask the organizers to register the same person every time (pick the person from the search instead of typing a new one).

## Step by step

### 1. Create the series

1. Log in as an organizer and open **Series** in the navigation bar.
2. Under *Start a series* enter the name and press **Create**. You manage the series. Add co-organizers under **Permissions** on the series page.
3. Open it and choose the settings: how to score, who is ranked, whether only the best legs count, and whether the series is **public**.

### 2. Add the contests

Open the series, **Legs**:

- **A contest you manage:** pick it in *Add a contest you manage* and press **Add**. It is a leg at once.
- **A contest somebody else manages** (another club's event): search for it under *Invite somebody else's contest*. The people who manage that contest get a request, and it becomes a leg when they accept.
- **From the contest side:** in the contest, *Contest access → Series*, choose a series and press **Ask**. If you manage the series it is added at once, otherwise the series managers get a request.

Requests wait under *Contests waiting to join* until somebody accepts, declines or cancels them.

The **leg number** sets the order of the legs in the table, and the **weight** how much a leg counts. Both can be changed at any time.

### 3. Follow the standings

The standings are worked out from the results of the contests whenever somebody opens the series, so they are always up to date; there is nothing to publish. A team appears when it is registered in at least one leg. The table can be downloaded as CSV.

## Who can do what

Access to a series works as for a contest. Open the series and use **Permissions** (shown to those who can manage it) to add people and choose a level for each:

| Level | Can do |
| :--- | :--- |
| **View** | See a private series and its standings. Nothing else. (Everybody can see a public series.) |
| **Manage** | Everything in *View*, plus change the settings, add and remove contests, answer requests, and **give others access, change their level or remove them** (except people with *Manage & delete*). |
| **Manage & delete** | Everything in *Manage*, plus delete the series and give or take away *Manage & delete* from others. |

Only **organizers** (people who pressed *Become an Organizer*) can be given *Manage* or *Manage & delete*; anybody with an account can be given *View*. The person who creates a series has *Manage & delete*. You cannot remove yourself or lower your own level below *Manage*, so a series is never left without somebody who manages it. Contest managers can always take their own contest out of a series.

## Visibility

- A **public** series is visible to everybody, and **every leg must be a public contest**. Make the contests public first; a contest that is in a public series cannot be made private until it leaves the series.
- A **private** series is visible only to the people you give access to (see below). It can contain private and public contests; use it to keep track of a cup before you publish it.

## Good to know

- Leaving or deleting: **Leave** in the contest, or **Remove** in the series, takes a contest out of the ranking. Deleting a series never deletes the contests or their results.
- A contest with no final result yet counts as no result for its teams. The standings fill in as the contests are scored.
- A contest that already holds a whole cup inside one contest can stay that way; you do not need to rebuild it as a series.
- Series standings are not in the mobile apps yet.

## Questions

**A pilot is missing or appears twice.** The entrant is the pilot's profile. If they were registered with two profiles, the series sees two people. Correct the registration in the contest.

**The ranking does not match my own sums.** Check the settings for scoring method, weights and *best N legs counted*; they are listed under the title of the series. Countback (more firsts) separates equal totals.

**Who can change the series?** Whoever has *Manage* or *Manage & delete* in the series permissions; the creator to begin with.
