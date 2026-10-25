import React from 'react';
import * as Sentry from '@sentry/react';
import { Link } from 'react-router-dom';
import routes from '../../routes.json';

interface RouteErrorBoundaryProps {
    children: React.ReactNode;
}

// Browsers phrase a failed dynamic import() differently (Chrome: "Failed to fetch dynamically
// imported module", Firefox: "error loading dynamically imported module", Safari: "Importing a
// module script failed") - match all three rather than one browser's wording. Vite's own
// "Unable to preload CSS for <url>" is the same stale-deploy failure for a chunk's stylesheet
// (Sentry JAVASCRIPT-REACT-K, JAVASCRIPT-REACT-16).
const CHUNK_LOAD_ERROR_PATTERN = /failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed|unable to preload css/i;

function isChunkLoadError(error: unknown): boolean {
    const message = error instanceof Error ? error.message : String(error);
    return CHUNK_LOAD_ERROR_PATTERN.test(message);
}

const CHUNK_RELOAD_GUARD_KEY = 'aslt-chunk-reload-attempted';
// A reload is not repeated within this long: a reload that did not help would otherwise loop. Later it is allowed
// again, as the next deploy of the tab's life makes its chunks stale in the same way.
const CHUNK_RELOAD_GUARD_MS = 60_000;
// Set when the guard declined to reload, so the fallback offers a button instead of waiting for a reload that is not coming.
let staleReloadDeclined = false;

/**
 * A dynamic import() 404ing means this tab's HTML/JS still references a chunk hash from a
 * since-replaced deploy (vite.config.js's emptyOutDir wipes and re-hashes assets_vite on every
 * build) - no in-place retry fixes that, only a fresh page load that picks up the current
 * release's chunk hashes. Seen twice in production on different pages (Sentry
 * JAVASCRIPT-REACT-X, JAVASCRIPT-REACT-15) as the generic "Something went wrong, reload" fallback
 * below, which the user has to notice and click themselves - do it for them instead.
 *
 * The guard is the time of the last automatic reload (not a flag that stays set for the tab's life, which left a
 * tab that had reloaded once stuck on "Updating..." at every later deploy). sessionStorage can be null (or throw)
 * when DOM storage is disabled - seen in production elsewhere already (JAVASCRIPT-REACT-Y, see
 * ContestantScheduling.tsx). Without a persistent guard we can't tell "stale build, one reload fixes it" apart from
 * "reload didn't help, this will just loop forever" - so without storage, skip the auto-reload entirely and fall back
 * to the normal fallback UI rather than risking a reload loop.
 */
function reloadOnceForStaleChunk(): void {
    try {
        const last = Number(sessionStorage.getItem(CHUNK_RELOAD_GUARD_KEY));
        if (last && Date.now() - last < CHUNK_RELOAD_GUARD_MS) {
            staleReloadDeclined = true;
            return;
        }
        sessionStorage.setItem(CHUNK_RELOAD_GUARD_KEY, String(Date.now()));
    } catch {
        staleReloadDeclined = true;
        return;
    }
    window.location.reload();
}

/**
 * Contains a rendering crash to the current page instead of letting it bubble up to the
 * single app-wide Sentry.ErrorBoundary in FrontendApp.tsx, which unmounts the entire SPA to
 * a blank "Something went wrong, reload the page" screen for every open tab/page, not just
 * the one that actually broke. FrontendRouter.tsx wraps each route in this with
 * `key={location.pathname}`, so navigating to a different page - even a different param on
 * the same route - remounts a fresh boundary instead of getting stuck showing this fallback.
 */
export default function RouteErrorBoundary({ children }: RouteErrorBoundaryProps) {
    return (
        <Sentry.ErrorBoundary
            onError={(error) => {
                if (isChunkLoadError(error)) {
                    reloadOnceForStaleChunk();
                }
            }}
            fallback={({ error }) => {
                if (isChunkLoadError(error)) {
                    return (
                        <div className="hero min-h-screen bg-base-200">
                            <div className="hero-content text-center">
                                {staleReloadDeclined ? (
                                    <div className="max-w-md">
                                        <p className="py-6">A new version is available. Reload the page to update.</p>
                                        <button className="btn btn-primary" onClick={() => window.location.reload()}>
                                            Reload
                                        </button>
                                    </div>
                                ) : (
                                    <p className="py-6">Updating to the latest version...</p>
                                )}
                            </div>
                        </div>
                    );
                }
                return (
                    <div className="hero min-h-screen bg-base-200">
                        <div className="hero-content text-center">
                            <div className="max-w-md">
                                <h1 className="text-2xl font-bold">Something went wrong</h1>
                                <p className="py-6">This page ran into an error. Reloading usually fixes it.</p>
                                <div className="flex gap-2 justify-center">
                                    <button className="btn btn-primary" onClick={() => window.location.reload()}>
                                        Reload
                                    </button>
                                    <Link to={routes.HOME} className="btn btn-ghost">
                                        Go home
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }}
        >
            {children}
        </Sentry.ErrorBoundary>
    );
}
