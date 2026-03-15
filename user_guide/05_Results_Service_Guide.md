# Results Service Guide: Managing the Leaderboard

The ASLT Results Service is the "Heart" of the competition. It is a real-time, synchronized scoring engine that aggregates results from automated tracking and manual entries. 

---

## 1. The Structure of Results

The Results Service operates with a clear hierarchy:

1.  **Contest:** The overall event (e.g., "National Championships 2024").
2.  **Tasks:** Major categories within a contest (e.g., "Navigation", "Landings", "Theory").
3.  **Tests:** Individual components of a task (e.g., "Landing 1", "Landing 2", "Task 1: Navigation").

### Automated vs. Manual
*   **Automated Tests:** These are linked directly to a **Navigation Task**. As pilots fly, their scores are pushed from the tracking calculators into these tests.
*   **Manual Tests:** These are for scores that cannot be tracked automatically (e.g., "Spot Landing" penalties recorded by judges on the ground).

---

## 2. Managing Manual Tasks and Tests

Organizers can add non-flying elements to the scoreboard with ease.

### Step 1: Create a Task
1.  Navigate to your Contest Results page.
2.  Click **"Add Task"**. Give it a name like "Ground Tests".
3.  **Weight:** You can assign a multiplier. If a task is worth 50% of the total score, set its weight accordingly.
4.  **Autosum:** Check this box so the system automatically sums all the tests within this task.

### Step 2: Create a Test
1.  Inside your new task, click **"Add Test"**.
2.  **Name:** e.g., "Theory Exam".
3.  **Sorting:**
    *   **Ascending:** Lowest score is best (e.g., Penalty points).
    *   **Descending:** Highest score is best (e.g., Percentage correct).
4.  **Weight:** Multiplier for this specific test.

### Step 3: Inputting Scores
Managers can enter scores directly into the results table. 
*   Simply click on the cell for a team and a test, and type the score.
*   The change is saved instantly and pushed to all active viewers.

---

## 3. The Clubhouse Scoreboard

The Results Service is designed for public display.

### Live Synchronization
ASLT uses **WebSockets** (specifically Django Channels) to ensure the scoreboard is always up to date.
*   When a pilot lands and their tracking calculator finalizes, their score appears on the scoreboard **instantly** without anyone needing to refresh the page.
*   The same applies to manual entries made by a judge.

### Sorting and Ranking
*   The system automatically calculates the **Task Summary** and the **Contest Summary**.
*   Ranking is updated in real-time. If a pilot's landing score moves them from 5th to 1st place, the entire table re-sorts itself immediately.

---

## 4. Configuration and Overrides

Access the **Management** button on the results page to find these settings:

*   **Summary Score Sorting Direction:** Defines the overall winner of the contest. (In Precision, the person with the *lowest* total penalty points wins, so set to **Ascending**).
*   **Autosum Scores:** Toggle this to define if the "Overall Total" should be the sum of everything or a manually entered value.
*   **Exporting Results:** You can export the entire scoreboard to a CSV file at any time for official reporting or archiving.
