# Results Service Guide: Managing the Leaderboard

The ASLT Results Service is the real-time leaderboard for a contest. It combines:

- automatically calculated scores from navigation tasks
- manually entered scores for other tests
- automatic task summaries
- automatic contest summaries
- live synchronization to all connected viewers

When an organizer changes the results table, the change is sent through the REST API and then pushed to all open clients through WebSockets.

---

## 1. The Structure of Results

The Results Service has a strict hierarchy:

1. **Contest**
   - The full event.
   - Example: `National Championships 2024`

2. **Tasks**
   - Major score categories inside the contest.
   - Example: `Navigation`, `Landings`, `Theory`

3. **Tests**
   - Individual scoring items inside a task.
   - Example: `Landing 1`, `Landing 2`, `Theory Exam`, `Navigation`

4. **Task Summary**
   - The total score for one team inside one task.
   - Usually calculated automatically from all tests inside that task.

5. **Contest Summary**
   - The total score for one team for the whole contest.
   - Usually calculated automatically from all task summaries.

---

## 2. Automatic Navigation Results

Whenever a **Navigation Task** is created in ASLT, the Results Service automatically creates:

- one linked **Task** in the Results Service
- one linked **Test** inside that task

This special test receives the score from the navigation calculator automatically.

### Important

This linked task/test pair is special:

- it stays synchronized with the navigation task
- the score is updated automatically from the tracker/calculator
- it should be treated as the "navigation results channel" for that navigation task
- it is not meant to be manually repurposed into a different kind of score item

In practice, this means:

- you can add **extra manual tests** inside the same task if you want to combine automatic navigation scoring with manual judging
- you can also create entirely new tasks and tests for unrelated score categories
- the navigation-linked task/test should remain the navigation-linked part of the structure

---

## 3. Understanding the Table Layout

The results table has two levels of view.

### 3.1 Overview mode

When you first open the Results Service, you see the **overview**.

The overview shows:

- the **Contest Summary** column (`Σ`)
- one column for each **Task**
- one row for each crew/team

This means the first view is intentionally compact:

- you see the contest total
- you see the task totals
- you do **not** initially see the individual tests

### 3.2 Task detail mode

To view the tests inside a task, you must click the **task heading**.

The task heading is the colored task title with a small arrow/chevron icon.
Example visual cue:

- `▾ Navigation`
- `▾ Landings`

When you click the task heading:

- that task expands
- the individual **tests** inside the task become visible
- the task summary remains visible as `Task Name (Σ)`

This is how you move from the overview to the detailed test view.

### Important limitation

You do **not** edit the score of a task summary directly when autosumming is in use.
To change the score for a task, you usually:

1. click the **task heading** to reveal its tests
2. edit the relevant **test** score(s)
3. let ASLT automatically recalculate the task summary and contest summary

So, if you want to change a score inside a task:
- first click the task heading
- then edit the test score(s)

---

## 4. Editor View vs Public View

Users with **change permissions** on the contest see the management version of the table.

They can:

- enter scores directly in editable cells
- create tasks
- create tests
- rename tasks and tests
- change weights
- reorder tasks and tests
- delete tasks and tests
- remove team results

Users without change permissions see a read-only table.

They can:

- view live results
- expand tasks to inspect tests
- export the CSV

They cannot:

- edit scores
- create tasks or tests
- reorder anything
- delete anything

---

## 5. Creating a New Task

A **new task is created from the overview page**.
Do not expand a task first if your goal is to create another top-level task.

### Where to click

On the overview table, look in the header of the contest summary column (`Σ`).
There is a small **plus-circle** button there.

Typical visual cue:

- `Σ   ⊕`

In the current UI this is the small **Add new task** icon next to the contest total header.

### Step-by-step

1. Open the Results Service.
2. Stay in the **overview**.
3. Find the contest summary header (`Σ`).
4. Click the **Add new task** icon (`⊕`).
5. Fill in the task form.
6. Click **Submit**.

### Task form fields

You will typically set:

- **Task Name**
  - The visible label of the task.
  - Example: `Landings`

- **Autosum test scores**
  - If enabled, ASLT automatically sums all tests inside the task into the task summary.
  - This is the normal setting for most tasks.

- **Task Weight**
  - Multiplies the final task summary before it contributes to the contest summary.

- **Score Sorting Direction**
  - `Ascending`: lower score is better
  - `Descending`: higher score is better

### Examples

Use **Ascending** for penalty-based tasks:
- navigation penalties
- landing penalties
- rule infractions

Use **Descending** for points-based tasks:
- quiz score
- observation points
- bonus points

---

## 6. Creating a New Test

A **new test is created after clicking a task heading**.

This is important:
- new tasks are created from the overview
- new tests are created inside an expanded task

### Where to click

1. Click the task heading to expand the task.
2. In the expanded task header area, click the **Add new test** icon (`⊕`).

Typical visual cue inside an expanded task header:

- `▾ Landings (Σ)   ⊕`

### Step-by-step

1. Open the Results Service.
2. Click the heading of the task where the test should belong.
3. Wait for the tests inside that task to appear.
4. Click the **Add new test** icon (`⊕`) in that task header.
5. Fill in the test form.
6. Click **Submit**.

### Test form fields

You will typically set:

- **Test Name**
  - Example: `Landing 1`
  - Example: `Theory Exam`
  - Example: `Observation Round 2`

- **Test Weight**
  - Multiplies this test before it contributes to the task summary.

- **Score Sorting Direction**
  - `Ascending`: lower is better
  - `Descending`: higher is better

### Examples

If a task called `Landings` contains 3 landings, you can create:
- `Landing 1`
- `Landing 2`
- `Landing 3`

If a task called `Ground Tests` contains two components, you can create:
- `Theory`
- `Aircraft Identification`

---

## 7. Entering and Editing Scores

### Editing a test score

To edit a score inside a task:

1. click the **task heading** to expand the task
2. locate the correct test column
3. click the cell for the relevant crew/team
4. type the score

The score is saved immediately and synchronized to all open clients.

### Important

If the task uses **Autosum test scores**, you usually do not manually edit the task summary.
Instead:

- edit the test score
- ASLT recalculates the task summary automatically
- ASLT recalculates the contest summary automatically

### Editing summary values

Directly editing a summary column is only meaningful if your setup intentionally uses manual summary values.
For ordinary usage:

- edit **tests**
- let summaries update automatically

---

## 8. How Auto Summarizing Works

There are two different automatic sums.

### 8.1 Task autosum

If **Autosum test scores** is enabled on a task:

Task Summary = sum of all weighted tests in that task

Formula:

`Task Summary = (Test 1 × Test 1 Weight) + (Test 2 × Test 2 Weight) + ...`

### Example

Task: `Landings`

Tests:
- `Landing 1 = 20`
- `Landing 2 = 30`
- `Landing 3 = 10`

If all test weights are `1.0`, then:

`Task Summary = 20 + 30 + 10 = 60`

If weights are:
- `Landing 1 weight = 1.0`
- `Landing 2 weight = 2.0`
- `Landing 3 weight = 1.0`

Then:

`Task Summary = (20×1.0) + (30×2.0) + (10×1.0) = 20 + 60 + 10 = 90`

### 8.2 Contest autosum

If contest autosumming is enabled:

Contest Summary = sum of all weighted task summaries

Formula:

`Contest Summary = (Task A Summary × Task A Weight) + (Task B Summary × Task B Weight) + ...`

### Example

Tasks:
- `Navigation Summary = 120`
- `Landings Summary = 60`

Task weights:
- `Navigation weight = 1.0`
- `Landings weight = 0.5`

Then:

`Contest Summary = (120×1.0) + (60×0.5) = 120 + 30 = 150`

---

## 9. Understanding the Weighting System

There are **two levels of weighting**:

### 9.1 Test weight

A test weight changes how much that test contributes inside its task.

Use this when one test inside a task should count more than another.

Example:
- `Landing 1 weight = 1.0`
- `Landing 2 weight = 2.0`

This means `Landing 2` counts twice as much as `Landing 1` in the task summary.

### 9.2 Task weight

A task weight changes how much the task contributes to the full contest summary.

Use this when one task should count more than another.

Example:
- `Navigation weight = 1.0`
- `Theory weight = 0.25`

This means the full theory task counts only 25% as much as navigation in the contest total.

### Practical advice

Use weights to express importance.

Examples:
- A minor theory quiz may have low task weight.
- A major navigation task may have full task weight.
- A bonus test inside a task may have reduced test weight.
- A critical test may have increased test weight.

---

## 10. Reordering Tasks and Tests

### Reordering tasks

Tasks can be moved left and right in the overview.

Look for the **left** and **right** arrow icons in the task header:

- `←` Move task left
- `→` Move task right

To reorder tasks:

1. stay in the overview, or expand a task if needed
2. find the task header
3. click the left/right arrow icon

### Reordering tests

Tests can also be moved left and right inside an expanded task.

Look for the **left** and **right** arrow icons next to the test header:

- `←` Move test left
- `→` Move test right

To reorder tests:

1. click the task heading to expand the task
2. find the specific test header
3. click the left/right arrow icon

---

## 11. Renaming, Editing, and Deleting

### Task controls

In a task header, editors may see icons such as:

- `✏` Edit task
- `🗑` Delete task
- `←` Move task left
- `→` Move task right
- `⊕` Add new test (visible when the task is expanded)

### Test controls

In a test header, editors may see icons such as:

- `✏` Edit test
- `🗑` Delete test
- `←` Move test left
- `→` Move test right

### Important for navigation-linked items

The automatically created navigation-linked task/test is special.
It represents the synchronized score channel for the navigation task.

Because of that:
- it should not be deleted from the Results Service
- it should not be repurposed into something else
- if you need extra scoring items related to the same navigation task, create additional manual tests inside the same task

---

## 12. Team Removal

Editors can remove a crew/team result row from the results table.

In the crew column, editors may see a delete icon:
- `🗑`

When used:
- the team is removed from the results listing for that contest
- the change is synchronized to all connected clients

Use this carefully.

---

## 13. Live Synchronization

The Results Service is designed for public and organizer use at the same time.

### What is synchronized live

The following changes are pushed live:

- score changes
- task changes
- test changes
- team result removal
- automatic navigation score updates

### What viewers experience

- public/view-only users see updates without refreshing
- organizers see the same live updates while editing
- CSV export reflects the current database state when downloaded

---

## 14. CSV Export

Any user can export the current results table as CSV.

Look for the **Export CSV** button in the upper-right area of the page.

Use this for:
- official reporting
- backup/export
- offline review
- importing into spreadsheets

---

## 15. Recommended Workflow for Organizers

### To add a completely new score category

1. stay on the overview page
2. click the **Add new task** icon next to `Σ`
3. create the task
4. click the task heading to expand it
5. click the **Add new test** icon inside that task
6. create one or more tests
7. enter scores in the test columns

### To add another score item to an existing task

1. click the task heading
2. click the **Add new test** icon
3. create the test
4. enter scores

### To modify the order

1. use left/right arrows on task headers for tasks
2. use left/right arrows on test headers for tests

### To edit scores correctly

1. expand the task first
2. edit the relevant test score
3. let ASLT recompute summaries automatically

---

## 16. Summary

Remember these key rules:

- The default page is the **overview**: contest summary + task summaries.
- Click a **task heading** to reveal the tests inside it.
- You usually edit **test scores**, not task summary scores.
- New **tasks** are created from the overview page.
- New **tests** are created after expanding a task.
- Test weights affect the task summary.
- Task weights affect the contest summary.
- Navigation-linked task/test entries are special and stay synchronized with navigation scoring.
- All changes are synchronized live across connected clients.
