/** What a key does on a display (broadcast or screen mode). */
export type DisplayKeyAction =
    | { kind: 'place'; place: number }
    | { kind: 'step'; by: 1 | -1 }
    | { kind: 'camera' }
    | { kind: 'overview' }
    | { kind: 'help' };

/** The keys, as listed by "?". */
export const DISPLAY_KEYS: [string, string][] = [
    ['1 to 9', 'Follow the contestant in that place'],
    ['← →', 'Follow the previous or next contestant in the air'],
    ['F', 'Turn the follow camera on or off'],
    ['Esc', 'Back to the whole field'],
    ['?', 'Show or hide these keys'],
];

/** The action for a key press, or null for keys that do nothing (and with a modifier held, so browser shortcuts work). */
export function displayKeyAction(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean }): DisplayKeyAction | null {
    if (e.ctrlKey || e.metaKey || e.altKey) return null;
    if (/^[1-9]$/.test(e.key)) return { kind: 'place', place: Number(e.key) };
    if (e.key === 'ArrowRight') return { kind: 'step', by: 1 };
    if (e.key === 'ArrowLeft') return { kind: 'step', by: -1 };
    if (e.key === 'f' || e.key === 'F') return { kind: 'camera' };
    if (e.key === 'Escape') return { kind: 'overview' };
    if (e.key === '?') return { kind: 'help' };
    return null;
}

/** The next contestant in the air after (or before) the one followed now; the first or last when nobody is. */
export function stepThrough(flyingIds: number[], current: number | null, by: 1 | -1): number | null {
    if (flyingIds.length === 0) return null;
    const i = current === null ? -1 : flyingIds.indexOf(current);
    if (i < 0) return by === 1 ? flyingIds[0] : flyingIds[flyingIds.length - 1];
    return flyingIds[(i + by + flyingIds.length) % flyingIds.length];
}
