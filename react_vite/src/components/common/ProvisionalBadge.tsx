import React, { useEffect, useId, useRef, useState } from 'react';

interface ProvisionalBadgeProps {
    /** Why the scores are provisional (utils/taskScore.ts provisionalHelp): the backend's short explanation. */
    text: string;
    /** "daisy" for the pages, "hud" for the dark panels of the live map. */
    variant?: 'daisy' | 'hud';
    label?: string;
    className?: string;
}

/**
 * The "Provisional" badge with its explanation. A tap or a click opens a small panel under the badge (a hover tooltip
 * does not exist on a phone); a tap elsewhere, or Escape, closes it. The text is also the badge's title, so a mouse
 * user gets it on hover too.
 */
const ProvisionalBadge: React.FC<ProvisionalBadgeProps> = ({ text, variant = 'daisy', label = 'Provisional', className = '' }) => {
    const [open, setOpen] = useState(false);
    const wrapperRef = useRef<HTMLSpanElement>(null);
    const panelId = useId();

    useEffect(() => {
        if (!open) return;
        const close = (event: Event) => {
            if (event instanceof KeyboardEvent) {
                if (event.key === 'Escape') setOpen(false);
            } else if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener('pointerdown', close);
        document.addEventListener('keydown', close);
        return () => {
            document.removeEventListener('pointerdown', close);
            document.removeEventListener('keydown', close);
        };
    }, [open]);

    const hud = variant === 'hud';
    return (
        <span ref={wrapperRef} className={`relative inline-block normal-case ${className}`}>
            <button
                type="button"
                data-testid="provisional-badge"
                title={text}
                aria-expanded={open}
                aria-controls={open ? panelId : undefined}
                onClick={() => setOpen(value => !value)}
                className={
                    hud
                        ? 'text-[11px] font-semibold px-1.5 rounded cursor-pointer underline decoration-dotted underline-offset-2'
                        : 'badge badge-warning badge-sm align-middle cursor-pointer gap-1'
                }
                style={hud ? { background: 'var(--hud-raised)', color: 'var(--hud-warn)' } : undefined}
            >
                {label}
                <span aria-hidden="true">?</span>
            </button>
            {open && (
                <span
                    id={panelId}
                    role="note"
                    data-testid="provisional-explanation"
                    className={`absolute right-0 top-full z-50 mt-1 w-64 max-w-[80vw] rounded-md p-2 text-left text-xs font-normal leading-snug whitespace-normal shadow-lg ${
                        hud ? 'border hud-divider' : 'bg-base-100 text-base-content border border-base-300'
                    }`}
                    style={hud ? { background: 'var(--hud-surface)', color: 'var(--hud-text)', boxShadow: '0 4px 12px var(--hud-shadow)' } : undefined}
                >
                    {text}
                </span>
            )}
        </span>
    );
};

export default ProvisionalBadge;
