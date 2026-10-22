import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { AUTH_FILE, settings } from "./config";

// npm run login
//
// Opens the site so you can log in as the user the tutorials are recorded as, then saves the session. Recordings and
// codegen start logged in from then on. Close the browser window when you are logged in.

const browser = await chromium.launch({ headless: false });
const context = await browser.newContext({ baseURL: settings.baseUrl, viewport: settings.viewport });
const page = await context.newPage();
await page.goto("/");
console.log("Log in, then close the browser window.");
await page.waitForEvent("close", { timeout: 0 });
mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
await context.storageState({ path: AUTH_FILE });
await browser.close();
console.log(`Saved the session to ${AUTH_FILE}`);
