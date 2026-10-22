import { existsSync } from "node:fs";
import { request } from "playwright";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { AUTH_FILE, SCRIPTS_DIR, settings, tutorialName } from "./config";
import type { CleanUp, Tutorial } from "./tutorial";

// Removes what an earlier recording of a tutorial created (routes and navigation tasks, by exact name), so the replay
// starts from the same state every time and does not find two of everything. Runs before every recording
// (npm run record) and on its own with npm run cleanup -- <tutorial>. Uses the site's API, logged in as the tutorial
// user. Only against the local site: names like "Task 2.A3" could match real data elsewhere.

type ContestPage = {
  next: string | null;
  results: { id: number; name: string; navigationtask_set?: { pk: number; name: string }[] }[];
};

export async function cleanUp(spec: CleanUp | undefined): Promise<void> {
  const routeNames = new Set(spec?.routes ?? []);
  const taskNames = new Set(spec?.navigationTasks ?? []);
  if (routeNames.size === 0 && taskNames.size === 0) return;
  const host = new URL(settings.baseUrl).hostname;
  if (!["localhost", "127.0.0.1"].includes(host) && process.env.TUTORIAL_ALLOW_CLEANUP !== "1") {
    throw new Error(`Not cleaning up on ${settings.baseUrl}: only the local site (set TUTORIAL_ALLOW_CLEANUP=1 to allow)`);
  }
  if (!existsSync(AUTH_FILE)) throw new Error("No saved login to clean up with: record the clicks once first");

  const api = await request.newContext({ baseURL: settings.baseUrl, storageState: AUTH_FILE });
  try {
    const csrf = (await api.storageState()).cookies.find((cookie) => cookie.name === "csrftoken")?.value ?? "";
    const remove = async (url: string, what: string) => {
      const response = await api.delete(url, { headers: { "X-CSRFToken": csrf, Referer: settings.baseUrl } });
      if (!response.ok()) throw new Error(`Could not delete ${what}: ${response.status()} ${await response.text()}`);
      console.log(`  cleaned up ${what}`);
    };

    // Tasks first: a task keeps its route
    if (taskNames.size > 0) {
      let url: string | null = "/api/v1/contests/";
      while (url) {
        const page = (await (await api.get(url)).json()) as ContestPage;
        for (const contest of page.results) {
          if (spec?.contest && contest.name !== spec.contest) continue;
          for (const task of contest.navigationtask_set ?? []) {
            if (taskNames.has(task.name)) {
              await remove(`/api/v1/contests/${contest.id}/navigationtasks/${task.pk}/`, `task "${task.name}" in "${contest.name}"`);
            }
          }
          if (spec?.contest) url = null;
        }
        if (url) url = page.next ? (page.next.startsWith("http") ? page.next : `/api/v1/contests/?cursor=${page.next}`) : null;
      }
    }

    if (routeNames.size > 0) {
      const routes = (await (await api.get("/api/v1/editableroutes/")).json()) as { id: number; name: string; is_editor?: boolean }[];
      for (const route of routes) {
        if (routeNames.has(route.name) && route.is_editor !== false) {
          await remove(`/api/v1/editableroutes/${route.id}/`, `route "${route.name}"`);
        }
      }
    }
  } finally {
    await api.dispose();
  }
}

// npm run cleanup -- <tutorial>: the same on its own, for example before recording the clicks again
if (process.argv[1]?.endsWith("cleanup.ts")) {
  const name = tutorialName(process.argv[2]);
  if (!name) {
    console.error("Usage: npm run cleanup -- <tutorial name>");
    process.exit(1);
  }
  const tutorial: Tutorial = (await import(pathToFileURL(path.join(SCRIPTS_DIR, `${name}.ts`)).href)).default;
  if (!tutorial.cleanUp) console.log(`${name} has no cleanUp: nothing to remove`);
  await cleanUp(tutorial.cleanUp);
}
