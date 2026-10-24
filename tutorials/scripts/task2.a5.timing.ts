import { defineTiming } from "../src/shared/timing";

// Timing changes for task2.a5, applied when the video is made: no new recording is needed to try them, and a new
// recording gets them too. Steps are named "<chapter> #<n>" (the n-th step since that chapter() line). Written by the
// timing editor (npm run timing -- task2.a5), which can be used to change them, or change them here.
export default defineTiming({
  steps: {
    "Task wizard #3": {
      holdMs: 1000
    },
    "Backbone route #1": {
      speed: 1.5,
      until: "Unknown leg 1 #1"
    },
    "Flight order #1": {
      holdMs: 1500
    }
  }
});
