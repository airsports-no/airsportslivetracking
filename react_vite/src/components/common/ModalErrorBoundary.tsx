import React from 'react';
import * as Sentry from '@sentry/react';

interface ModalErrorBoundaryProps {
    children: React.ReactNode;
    onReset: () => void;
}

/**
 * Contains a rendering crash to the modal it wraps instead of letting it bubble up to the
 * single app-wide Sentry.ErrorBoundary in FrontendApp.tsx, which unmounts the entire SPA to
 * a blank "Something went wrong, reload the page" screen. Modals are the most volatile part
 * of the tree (mounted/unmounted via portals, often rendering right as unrelated data
 * fetches resolve), so a reconciliation hiccup there - most commonly a benign
 * insertBefore/removeChild NotFoundError from something outside React mutating document.body
 * (a browser extension, another widget) - shouldn't take down pages the user wasn't even
 * looking at.
 */
export default function ModalErrorBoundary({ children, onReset }: ModalErrorBoundaryProps) {
    return (
        <Sentry.ErrorBoundary
            onReset={onReset}
            fallback={({ resetError }) => (
                <div className="fixed inset-0 bg-black/50 z-[9999] flex justify-center items-center p-4">
                    <div className="card bg-base-100 shadow-xl max-w-md w-full">
                        <div className="card-body items-center text-center gap-3">
                            <p>Something went wrong opening this dialog. Please try again.</p>
                            <button type="button" className="btn btn-primary" onClick={resetError}>
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        >
            {children}
        </Sentry.ErrorBoundary>
    );
}
