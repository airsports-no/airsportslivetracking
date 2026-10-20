---
layout: ../../layouts/DocsLayout.astro
title: "How ASLT Works: The Big Picture"
---

# How ASLT Works: The Big Picture

New to Air Sports Live Tracking? This page explains the handful of ideas that everything else is built on. It takes about five minutes, and it will make every other guide easier to follow.

---

## The building blocks

| Term | What it is | Example |
| :--- | :--- | :--- |
| **Contest** | The event: a name, dates, a location and a group of people. It holds everything else. | "Spring Precision Cup 2026" |
| **Route** | A reusable flight path made of waypoints, gates and turns. A route lives on its own, outside any contest, and you draw it in the *route editor* (an "editable route"). | "Mountain triangle, 38 NM" |
| **Navigation Task** | One flown event inside a contest: a route plus a scoring ruleset (a *scorecard*). A contest usually has several tasks, one per flight. | "Saturday morning: Precision" |
| **Team** | The people and aeroplane that take part: pilot, optional co-pilot, aircraft registration. A team registers once **per contest**. | "Anna + Ben in LN-ABC" |
| **Contestant** | One team flying one navigation task, with a start time. This is "a flight". | "Anna + Ben, Saturday morning, start 09:42" |
| **Series** | A cup or championship: several contests ranked together, where a team's places in the contests are added up. | "Norwegian Cup 2026" |
| **Squadron** | A group of people (a club, a national team, friends) that you can share private contests with, so you do not have to add them one by one. | "LN national team" |

## How they fit together

<figure class="aslt-diagram">
<style>
  .aslt-diagram { margin: 2.5rem 0; }
  .aslt-diagram svg.wide, .aslt-diagram svg.narrow { width: 100%; height: auto; font-family: Inter, system-ui, sans-serif; }
  .aslt-diagram svg.narrow { display: none; max-width: 420px; margin: 0 auto; }
  @media (max-width: 640px) { .aslt-diagram svg.wide { display: none; } .aslt-diagram svg.narrow { display: block; } }
  .aslt-diagram figcaption { text-align: center; font-size: 0.9rem; color: #64748b; margin-top: 0.5rem; }
</style>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <marker id="fit-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#475569"/></marker>
    <marker id="fit-arrow-light" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#94a3b8"/></marker>
  </defs>
</svg>
<svg class="wide" viewBox="0 0 820 500" role="img" aria-labelledby="fit-wide-title fit-wide-desc">
  <title id="fit-wide-title">How contests, tasks, teams and contestants fit together</title>
  <desc id="fit-wide-desc">A route and a scorecard are copied into a navigation task. A pilot and an aircraft form a team. The task and the team both belong to a contest. A team that books a start time on a task is a contestant: one flight. Optionally, a series ranks several contests together, and a squadron is a group of people who may open a private contest.</desc>
  <rect x="235" y="24" width="370" height="350" rx="22" fill="#eff6ff" stroke="#93c5fd" stroke-width="2"/>
  <text x="257" y="54" font-size="13" font-weight="800" letter-spacing="2" fill="#1d4ed8">CONTEST</text>
  <text x="345" y="54" font-size="12.5" fill="#3b82f6">the event: dates, place, people</text>
  <rect x="10" y="70" width="155" height="66" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="87.5" y="100.0" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">Route</text>
  <text x="87.5" y="118.0" text-anchor="middle" font-size="12.5" fill="#64748b">reusable flight path</text>
  <rect x="10" y="176" width="155" height="66" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="87.5" y="206.0" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">Scorecard</text>
  <text x="87.5" y="224.0" text-anchor="middle" font-size="12.5" fill="#64748b">the scoring rules</text>
  <rect x="255" y="80" width="160" height="72" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="335.0" y="113.0" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">Navigation Task</text>
  <text x="335.0" y="131.0" text-anchor="middle" font-size="12.5" fill="#64748b">one flown event</text>
  <rect x="425" y="80" width="160" height="72" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="505.0" y="113.0" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">Team</text>
  <text x="505.0" y="131.0" text-anchor="middle" font-size="12.5" fill="#64748b">registers once</text>
  <rect x="650" y="80" width="160" height="72" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="730.0" y="113.0" text-anchor="middle" font-size="17" font-weight="700" fill="#1e293b">Pilot + aircraft</text>
  <text x="730.0" y="131.0" text-anchor="middle" font-size="12.5" fill="#64748b">people and plane</text>
  <rect x="325" y="252" width="190" height="82" rx="14" fill="#2563EB" stroke="#1d4ed8" stroke-width="1.5"/>
  <text x="420.0" y="290.0" text-anchor="middle" font-size="17" font-weight="700" fill="#ffffff">Contestant</text>
  <text x="420.0" y="308.0" text-anchor="middle" font-size="12.5" fill="#dbeafe">a team on a task: one flight</text>
  <rect x="235" y="412" width="175" height="66" rx="14" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 5"/>
  <text x="322.5" y="442.0" text-anchor="middle" font-size="17" font-weight="700" fill="#334155">Series</text>
  <text x="322.5" y="460.0" text-anchor="middle" font-size="12.5" fill="#64748b">ranks several contests</text>
  <rect x="430" y="412" width="175" height="66" rx="14" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 5"/>
  <text x="517.5" y="442.0" text-anchor="middle" font-size="17" font-weight="700" fill="#334155">Squadron</text>
  <text x="517.5" y="460.0" text-anchor="middle" font-size="12.5" fill="#64748b">may open a private contest</text>
  <path d="M165 103 C 215 103, 220 110, 253 112" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <path d="M165 209 C 222 209, 224 136, 253 132" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <text x="200" y="150" text-anchor="middle" font-size="12" fill="#475569" font-style="italic">copied</text>
  <text x="200" y="165" text-anchor="middle" font-size="12" fill="#475569" font-style="italic">into</text>
  <path d="M650 116 L 587 116" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <text x="618" y="106" text-anchor="middle" font-size="12" fill="#475569" font-style="italic">form a</text>
  <path d="M335 152 C 335 205, 370 215, 385 250" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <path d="M505 152 C 505 205, 470 215, 455 250" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <text x="517" y="208" text-anchor="start" font-size="12" fill="#475569" font-style="italic">books a start time</text>
  <path d="M322 412 L 322 378" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#fit-arrow-light)"/>
  <path d="M517 412 L 517 378" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#fit-arrow-light)"/>
</svg>
<svg class="narrow" viewBox="0 0 360 560" role="img" aria-labelledby="fit-narrow-title fit-narrow-desc">
  <title id="fit-narrow-title">How contests, tasks, teams and contestants fit together</title>
  <desc id="fit-narrow-desc">A route and a scorecard are copied into a navigation task. A pilot and an aircraft form a team. The task and the team both belong to a contest. A team that books a start time on a task is a contestant: one flight. Optionally, a series ranks several contests together, and a squadron is a group of people who may open a private contest.</desc>
  <rect x="8" y="14" width="108" height="62" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="62.0" y="42.0" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Route</text>
  <text x="62.0" y="60.0" text-anchor="middle" font-size="11.5" fill="#64748b">flight path</text>
  <rect x="126" y="14" width="108" height="62" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="180.0" y="42.0" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Scorecard</text>
  <text x="180.0" y="60.0" text-anchor="middle" font-size="11.5" fill="#64748b">scoring rules</text>
  <rect x="244" y="14" width="108" height="62" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="298.0" y="42.0" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Pilot + plane</text>
  <text x="298.0" y="60.0" text-anchor="middle" font-size="11.5" fill="#64748b">form a team</text>
  <rect x="8" y="118" width="344" height="310" rx="20" fill="#eff6ff" stroke="#93c5fd" stroke-width="2"/>
  <text x="24" y="144" font-size="12" font-weight="800" letter-spacing="2" fill="#1d4ed8">CONTEST</text>
  <text x="112" y="144" font-size="11.5" fill="#3b82f6">the event</text>
  <rect x="22" y="160" width="150" height="66" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="97.0" y="190.0" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Navigation Task</text>
  <text x="97.0" y="208.0" text-anchor="middle" font-size="11.5" fill="#64748b">one flown event</text>
  <rect x="188" y="160" width="150" height="66" rx="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="263.0" y="190.0" text-anchor="middle" font-size="15" font-weight="700" fill="#1e293b">Team</text>
  <text x="263.0" y="208.0" text-anchor="middle" font-size="11.5" fill="#64748b">registers once</text>
  <rect x="85" y="318" width="190" height="80" rx="14" fill="#2563EB" stroke="#1d4ed8" stroke-width="1.5"/>
  <text x="180.0" y="355.0" text-anchor="middle" font-size="16" font-weight="700" fill="#ffffff">Contestant</text>
  <text x="180.0" y="373.0" text-anchor="middle" font-size="11.5" fill="#dbeafe">a team on a task: one flight</text>
  <path d="M62 76 L 80 157" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <path d="M180 76 L 120 157" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <text x="96" y="100" text-anchor="start" font-size="12" fill="#475569" font-style="italic">copied into</text>
  <path d="M298 76 L 270 157" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <path d="M97 226 C 97 270, 140 280, 155 315" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <path d="M263 226 C 263 270, 220 280, 205 315" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#fit-arrow)"/>
  <text x="275" y="285" text-anchor="start" font-size="12" fill="#475569" font-style="italic">books a</text>
  <text x="275" y="299" text-anchor="start" font-size="12" fill="#475569" font-style="italic">start time</text>
  <rect x="8" y="470" width="168" height="72" rx="14" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 5"/>
  <text x="92.0" y="503.0" text-anchor="middle" font-size="15" font-weight="700" fill="#334155">Series</text>
  <text x="92.0" y="521.0" text-anchor="middle" font-size="11.5" fill="#64748b">ranks several contests</text>
  <rect x="184" y="470" width="168" height="72" rx="14" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="6 5"/>
  <text x="268.0" y="503.0" text-anchor="middle" font-size="15" font-weight="700" fill="#334155">Squadron</text>
  <text x="268.0" y="521.0" text-anchor="middle" font-size="10.5" fill="#64748b">may open a private contest</text>
  <path d="M92 470 L 92 434" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#fit-arrow-light)"/>
  <path d="M268 470 L 268 434" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#fit-arrow-light)"/>
</svg>
<figcaption>Solid boxes are what every contest has; dashed boxes are optional.</figcaption>
</figure>

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
3. **Draw or import a route** in the route editor (**Route editor** in the navigation bar). Save it.
4. **Create a navigation task** inside the contest: pick a task type, pick the route, check the details.
5. **Add teams**, either yourself, by import, or by letting pilots register. Then **schedule** start times, or turn on *self-management* so pilots book their own.
6. **Generate flight orders** and share the contest link.

Two optional tools you can ignore on your first contest:

- **Squadron:** if your contest is private and a group of people should see it and fly in it, put them in a [squadron](/docs/13_Squadrons) and share the contest with it.
- **Series:** if several contests together make a cup or championship, rank them in a [series](/docs/14_Series). A single event with several tasks is one contest, not a series.

A good first step is to make a private "Test Competition" with one route, one task and one test team, and walk through it before your real event. The [Contest Manager Guide](/docs/03_Contest_Manager_Guide) and [Route Creation guide](/docs/04_Route_Creation_and_Tasks) cover each step in detail.

## Common questions

**Why can't I see my flight?** The website matches you to your flights by email address. If the organizer registered a different email than the one you log in with, ask them to correct it.

**Why can't pilots see my task?** For self-registration, the contest must be visible to the pilot (public, or shared with them directly or through a [squadron](/docs/13_Squadrons)), the task must be public, and *Allow self-management* must be on.

**Can I change a route after creating a task?** A task keeps its own copy of the route, so editing the original does not change tasks that already exist. Use *Edit route* on the task to change that task's copy.
