import React from 'react';
import * as Sentry from '@sentry/react';
import { Link } from 'react-router-dom';
import routes from '../../routes.json';

interface RouteErrorBoundaryProps {
    children: React.ReactNode;
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
            fallback={() => (
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
            )}
        >
            {children}
        </Sentry.ErrorBoundary>
    );
}
