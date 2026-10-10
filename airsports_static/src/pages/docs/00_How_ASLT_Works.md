---
layout: ../../layouts/DocsLayout.astro
title: "How ASLT Works: The Big Picture"
---

# How ASLT Works: The Big Picture

New to Air Sports Live Tracking? This page explains the handful of ideas that everything else is built on. It takes about five minutes, and it will make every other guide easier to follow.

---

## The five building blocks

| Term | What it is | Example |
| :--- | :--- | :--- |
| **Contest** | The event: a name, dates, a location and a group of people. It holds everything else. | "Spring Precision Cup 2026" |
| **Route** | A reusable flight path made of waypoints, gates and turns. A route lives on its own, outside any contest, and you draw it in the *route editor* (an "editable route"). | "Mountain triangle, 38 NM" |
| **Navigation Task** | One flown event inside a contest: a route plus a scoring ruleset (a *scorecard*). A contest usually has several tasks, one per flight. | "Saturday morning: Precision" |
| **Team** | The people and aeroplane that take part: pilot, optional co-pilot, aircraft registration. A team registers once **per contest**. | "Anna + Ben in LN-ABC" |
| **Contestant** | One team flying one navigation task, with a start time. This is "a flight". | "Anna + Ben, Saturday morning, start 09:42" |

## How they fit together

```
Route ────────────┐
                  ├──▶  Navigation Task  ──┐
Scorecard ────────┘                        │ belongs to
                                           ▼
Pilot + aircraft ──▶  Team  ──registers──▶ Contest
                                           │
          Team + Navigation Task  ═══▶  Contestant  (one flight)
```

Three rules of thumb:

1. **A route is a blueprint.** Many tasks, in many contests, can be created from the same route. Each task gets its own copy of the route and scorecard, so you can tweak a task without touching the original.
2. **A team belongs to a contest, a contestant belongs to a task.** Register your team once; then book a start time for each task you want to fly. Each booking creates one contestant.
3. **Scores belong to contestants.** The contest results add up the contestant scores across tasks.

## If you are a pilot

1. Create an account at **app.airsports.no** and install the mobile app. Use the **same email** in both.
2. Open the contest and click **Register team**. If the organizer has already added you, you will see your flight straight away.
3. For each task, click **Book start time** and pick when you want to start. Your flight order (maps, photos and times) is emailed to you.
4. On the day, open the app and press **Start tracking**. Your flight shows up under **My flights** on the website, with the results afterwards.

See the [Contestant Guide](/docs/02_Contestant_Guide) for details.

## If you are an organizer

1. Click **Become an Organizer** on the platform (it is instant).
2. **Create a contest.** Contests are private until you change the visibility in the contest settings.
3. **Draw or import a route** in the route editor (Management → Route editor). Save it.
4. **Create a navigation task** inside the contest: pick a task type, pick the route, check the details.
5. **Add teams**, either yourself, by import, or by letting pilots register. Then **schedule** start times, or turn on *self-management* so pilots book their own.
6. **Generate flight orders** and share the contest link.

A good first step is to make a private "Test Competition" with one route, one task and one test team, and walk through it before your real event. The [Contest Manager Guide](/docs/03_Contest_Manager_Guide) and [Route Creation guide](/docs/04_Route_Creation_and_Tasks) cover each step in detail.

## Common questions

**Why can't I see my flight?** The website matches you to your flights by email address. If the organizer registered a different email than the one you log in with, ask them to correct it.

**Why can't pilots see my task?** For self-registration, the contest must be visible, the task must be public and featured, and *Allow self-management* must be on.

**Can I change a route after creating a task?** A task keeps its own copy of the route, so editing the original does not change tasks that already exist. Use *Edit route* on the task to change that task's copy.
