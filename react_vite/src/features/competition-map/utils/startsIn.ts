/** "4:12", "2:38:00", or from a day ahead "34 d" (hours on end would not read). */
export function formatStartsIn(totalSeconds: number): string {
    const s = Math.max(0, Math.floor(totalSeconds));
    if (s >= 86400) return `${Math.floor(s / 86400)} d`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const pad = (n: number) => String(n).padStart(2, '0');
    return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}
