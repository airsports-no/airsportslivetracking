import React, { useState } from 'react';

export const DOCS_BASE_URL = 'https://airsports.no/docs';
export const CONCEPTS_DOC_URL = `${DOCS_BASE_URL}/00_How_ASLT_Works`;

interface ConceptHintProps {
    /** Stable id; dismissal is remembered per id in this browser. */
    id: string;
    title: string;
    children: React.ReactNode;
    learnMoreUrl?: string;
    className?: string;
}

const storageKey = (id: string) => `aslt-hint-dismissed:${id}`;

const readDismissed = (id: string): boolean => {
    try {
        return window.localStorage.getItem(storageKey(id)) === '1';
    } catch {
        return false;
    }
};

/** Dismissible explainer box for introducing a concept where it first matters. */
const ConceptHint: React.FC<ConceptHintProps> = ({ id, title, children, learnMoreUrl = CONCEPTS_DOC_URL, className = '' }) => {
    const [dismissed, setDismissed] = useState(() => readDismissed(id));

    if (dismissed) {
        return null;
    }

    const dismiss = () => {
        setDismissed(true);
        try {
            window.localStorage.setItem(storageKey(id), '1');
        } catch {
            // Storage unavailable (private window etc.); the hint just reappears next visit.
        }
    };

    return (
        <div role="note" className={`alert alert-info alert-soft items-start ${className}`}>
            <div className="flex-1 text-sm">
                <div className="font-bold">{title}</div>
                <div className="mt-1">{children}</div>
                <a href={learnMoreUrl} target="_blank" rel="noreferrer" className="link link-primary mt-2 inline-block">
                    Learn more
                </a>
            </div>
            <button type="button" className="btn btn-ghost btn-xs" onClick={dismiss} aria-label="Dismiss hint">
                Got it
            </button>
        </div>
    );
};

export default ConceptHint;
