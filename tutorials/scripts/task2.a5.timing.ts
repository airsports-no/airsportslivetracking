import { defineTiming } from "../src/shared/timing";

// Timing changes for task2.a5, applied when the video is made: no new recording is needed to try them, and a new
// recording gets them too. Steps are named "<chapter> #<n>" (the n-th step since that chapter() line): list them with
// npm run steps -- task2.a5, or see the current one at the top left of the picture in Remotion Studio.
export default defineTiming({
  // How still stretches are cut: longer than minGapMs is shortened to keepGapMs
  // edit: { minGapMs: 700, keepGapMs: 250 },
  steps: {
    // Twice as fast from this step until the step "until" (by default the next one):
    // "Placing the points #3": { speed: 2, until: "Placing the points #12" },
    // The picture held 1.5 s longer before this step (negative: that much less of the wait before it):
    // "Placing the points #12": { holdMs: 1500 },
    // A say() step: start the line 0.5 s earlier, let the next step wait for it, and say something else:
    // "Placing the points #1": { delayMs: -500, wait: true, text: "..." },
  },
});
