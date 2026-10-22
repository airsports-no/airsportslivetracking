import { defineTutorial } from "../src/runner/tutorial";

// A starting point: copy this file, record the clicks with `npm run codegen`, paste them between the say() lines.
export default defineTutorial({
  title: "Finding your way around",
  subtitle: "Where to find your contests",
  // Shown above the title and in the header during the video
  series: "Getting started",
  // On the end screen, when there is a next tutorial to watch
  next: "Creating a contest",
  startUrl: "/",
  async run({ page, say, highlight, camera, map }) {
    camera("wide");
    await say("Welcome to Air Sports Live Tracking. This short tour shows where to find your contests.");
    camera("auto");
    await highlight(page.locator("nav").first(), { label: "The main menu" });
    await say("Everything you manage starts from the menu at the top.", { wait: false });
    await page.locator("nav a").first().click();
  },
});
