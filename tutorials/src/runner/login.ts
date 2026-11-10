import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { AUTH_FILE, settings } from "./config";

// npm run login
//
// Opens the site so you can log in as the user the tutorials are recorded as, then saves the session. Recordings and
// codegen start logged in from then on. Close the browser window when you are logged in.

const launchOptions = {
  headless: false,
  // Prevent Google / OAuth providers from rejecting the browser as "automated / not trusted"
  ignoreDefaultArgs: ["--enable-automation"],
  args: ["--disable-blink-features=AutomationControlled"],
};

let browser;
const preferredChannel = process.env.TUTORIAL_BROWSER_CHANNEL?.trim();
if (preferredChannel) {
  browser = await chromium.launch({ ...launchOptions, channel: preferredChannel });
} else {
  try {
    // Prefer installed Google Chrome if present so Google OAuth trusts the browser completely
    browser = await chromium.launch({ ...launchOptions, channel: "chrome" });
  } catch {
    browser = await chromium.launch(launchOptions);
  }
}

const context = await browser.newContext({
  baseURL: settings.baseUrl,
  viewport: settings.viewport,
  storageState: existsSync(AUTH_FILE) ? AUTH_FILE : undefined,
});
const page = await context.newPage();
await page.goto("/accounts/login/");
console.log("Log in, then close the browser window.");
await page.waitForEvent("close", { timeout: 0 });
mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
await context.storageState({ path: AUTH_FILE });
await browser.close();
console.log(`Saved the session to ${AUTH_FILE}`);
