import React from 'react';
import * as Sentry from '@sentry/react';
import { Link } from 'react-router-dom';
import routes from '../../routes.json';

interface RouteErrorBoundaryProps {
    children: React.ReactNode;
}

// Browsers phrase a failed dynamic import() differently (Chrome: "Failed to fetch dynamically
// imported module", Firefox: "error loading dynamically imported module", Safari: "Importing a
// module script failed") - match all three rather than one browser's wording.
const CHUNK_LOAD_ERROR_PATTERN = /failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed/i;

function isChunkLoadError(error: unknown): boolean {
    const message = error instanceof Error ? error.message : String(error);
    return CHUNK_LOAD_ERROR_PATTERN.test(message);
}

const CHUNK_RELOAD_GUARD_KEY = 'aslt-chunk-reload-attempted';

/**
 * A dynamic import() 404ing means this tab's HTML/JS still references a chunk hash from a
 * since-replaced deploy (vite.config.js's emptyOutDir wipes and re-hashes assets_vite on every
 * build) - no in-place retry fixes that, only a fresh page load that picks up the current
 * release's chunk hashes. Seen twice in production on different pages (Sentry
 * JAVASCRIPT-REACT-X, JAVASCRIPT-REACT-15) as the generic "Something went wrong, reload" fallback
 * below, which the user has to notice and click themselves - do it for them instead.
 *
 * sessionStorage can be null (or throw) when DOM storage is disabled - seen in production
 * elsewhere already (JAVASCRIPT-REACT-Y, see ContestantScheduling.tsx). Without a persistent
 * guard we can't tell "stale build, one reload fixes it" apart from "reload didn't help, this
 * will just loop forever" - so without storage, skip the auto-reload entirely and fall back to
 * the normal fallback UI rather than risking a reload loop.
 */
function reloadOnceForStaleChunk(): void {
    try {
        if (sessionStorage.getItem(CHUNK_RELOAD_GUARD_KEY)) return;
        sessionStorage.setItem(CHUNK_RELOAD_GUARD_KEY, '1');
    } catch {
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
                                <p className="py-6">Updating to the latest version...</p>
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
