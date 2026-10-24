import { describe, expect, it } from "vitest";
import { addLagSample, clockOffsetMs, formatCountdown, formatOffset, secondsToRequiredTime, withinGrace } from "./gateCountdown";

const T = Date.UTC(2026, 9, 24, 12, 0, 0);

describe("gate countdown", () => {
    it("takes the smallest recent lag, since latency only adds", () => {
        let samples: number[] = [];
        samples = addLagSample(samples, T + 1800, T);
        samples = addLagSample(samples, T + 1200, T);
        samples = addLagSample(samples, T + 2500, T);
        expect(clockOffsetMs(samples, 0)).toBe(1200);
    });

    it("keeps the calculation delay apart from the clock offset", () => {
        // Browser 3 s ahead of the position times, 2 minutes calculation delay, 0.5 s latency.
        const samples = addLagSample([], T + 120_000 + 3_000 + 500, T);
        const offset = clockOffsetMs(samples, 2)!;
        expect(offset).toBe(3_500);
        // The message arrived when the map was at the position time T, 30 s before the gate's required time.
        expect(secondsToRequiredTime(T + 123_500, T + 30_000, offset, 2)).toBeCloseTo(30);
        expect(secondsToRequiredTime(T + 123_500 + 31_000, T + 30_000, offset, 2)).toBeCloseTo(-1);
    });

    it("only looks back over the recent messages", () => {
        let samples = addLagSample([], T + 10, T);
        for (let i = 0; i < 30; i++) samples = addLagSample(samples, T + 1000, T);
        expect(clockOffsetMs(samples, 0)).toBe(1000);
        expect(clockOffsetMs([], 0)).toBeNull();
    });

    it("formats like a stopwatch", () => {
        expect(formatCountdown(65)).toBe("1:05");
        expect(formatCountdown(0.2)).toBe("0:01");
        expect(formatCountdown(0)).toBe("0:00");
        expect(formatCountdown(-4.5)).toBe("+0:04");
        expect(formatOffset(2.6)).toBe("+3 s");
        expect(formatOffset(-2)).toBe("-2 s");
    });

    it("judges the offset against the grace period on each side", () => {
        expect(withinGrace(-2, 2, 2)).toBe(true);
        expect(withinGrace(-3, 2, 5)).toBe(false);
        expect(withinGrace(5, 2, 5)).toBe(true);
    });
});
