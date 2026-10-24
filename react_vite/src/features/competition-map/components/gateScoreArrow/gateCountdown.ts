// The gate score arrow's countdown to the next gate's required time, ticked in the browser between the server's
// crossing_time messages.
//
// The countdown runs on the map's own time: positions are scored (and these messages sent) only once the task's
// calculation delay has passed, and the browser's clock need not match the position times (GPS). Every message gives
// the time of the position it was made from, so arrival time minus position time is the browser's clock offset plus
// the calculation delay plus the network latency. Latency only ever adds, so the smallest recent value is the best
// estimate, and the browser's "now" minus that value is the position time the map is currently at.

/** How many recent messages the lag estimate looks back over. */
const LAG_SAMPLES = 30;

/** Arrival minus position time (milliseconds) of the recent messages, newest last. */
export function addLagSample(samples: number[], receivedAtMs: number, positionTimeMs: number): number[] {
    const next = [...samples, receivedAtMs - positionTimeMs];
    return next.length > LAG_SAMPLES ? next.slice(next.length - LAG_SAMPLES) : next;
}

/**
 * The browser's clock offset from the position times (milliseconds, positive when the browser is ahead), with the
 * task's calculation delay taken out. Null before the first message that carries a position time.
 */
export function clockOffsetMs(samples: number[], calculationDelayMinutes: number): number | null {
    if (samples.length === 0) return null;
    return Math.min(...samples) - (calculationDelayMinutes || 0) * 60_000;
}

/**
 * Seconds left until the required time (negative once it has passed), on the map's time: the browser's now, corrected
 * by the clock offset and held back by the calculation delay.
 */
export function secondsToRequiredTime(
    nowMs: number,
    expectedTimeMs: number,
    offsetMs: number,
    calculationDelayMinutes: number,
): number {
    const mapTimeMs = nowMs - offsetMs - (calculationDelayMinutes || 0) * 60_000;
    return (expectedTimeMs - mapTimeMs) / 1000;
}

/** "1:05" while counting down (rounded up, so it shows 0:00 exactly at the required time), "+0:04" once it has passed. */
export function formatCountdown(secondsLeft: number): string {
    const late = secondsLeft < 0;
    const whole = late ? Math.floor(-secondsLeft) : Math.ceil(secondsLeft);
    const minutes = Math.floor(whole / 60);
    const seconds = whole % 60;
    return `${late ? "+" : ""}${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** "+3 s", "-2 s" or "0 s". */
export function formatOffset(seconds: number): string {
    const rounded = Math.round(seconds);
    return `${rounded > 0 ? "+" : ""}${rounded} s`;
}

/** Whether a crossing this many seconds off the required time (positive: late) lies within the gate's grace period. */
export function withinGrace(offsetSeconds: number, graceBefore: number, graceAfter: number): boolean {
    return offsetSeconds < 0 ? -offsetSeconds <= graceBefore : offsetSeconds <= graceAfter;
}
