import React from "react";

/*
 * The gate score arrow: a timing scale from early to late with the gate's grace period in the middle, the penalty
 * points marked along it, and a pointer at the predicted (or, once final, the actual) crossing with its points.
 * Drawn as SVG in the map panel's colours (components/hud/hud.css), so it sits in the follow bar instead of on a
 * light card of its own. The scale is logarithmic from the middle, as it always was, so the seconds that matter
 * most near the gate get most of the width.
 */

const SIDE_PADDING = 28; // room for the end labels and the outermost values
const POINTER_MOVE_MS = 1000;

interface GateScoreArrowRendererProps {
    width: number;
    height: number;
    pointsPerSecond: number;
    maximumTimingPenalty: number;
    gracePeriodBefore: number;
    gracePeriodAfter: number;
    crossingOffsetEstimate: number;
    estimatedScore: number;
    contestantId: number;
    final: boolean;
    missed: boolean;
}

const GateScoreArrowRenderer: React.FC<GateScoreArrowRendererProps> = ({
    width,
    height,
    pointsPerSecond,
    maximumTimingPenalty,
    gracePeriodBefore,
    gracePeriodAfter,
    crossingOffsetEstimate,
    estimatedScore,
    final,
    missed,
}) => {
    const grace = Math.max(gracePeriodBefore, gracePeriodAfter);
    // How far the scale reaches: until the maximum penalty is reached (a minute past the grace period when the
    // scorecard has no per-second penalty, so the scale still has a sensible width).
    const maximumSeconds = Math.max(
        2,
        pointsPerSecond > 0 && maximumTimingPenalty > 0 ? grace + maximumTimingPenalty / pointsPerSecond : grace + 60,
    );
    const centre = width / 2;
    const sideLength = Math.max(1, centre - SIDE_PADDING);
    const perLogSecond = sideLength / Math.log10(maximumSeconds + 1);
    const secondsToX = (seconds: number) => {
        const clamped = Math.max(-maximumSeconds, Math.min(maximumSeconds, seconds));
        const distance = Math.log10(Math.abs(clamped) + 1) * perLogSecond;
        return clamped < 0 ? centre - distance : centre + distance;
    };
    const secondsToPoints = (seconds: number) => {
        const allowed = seconds < 0 ? gracePeriodBefore : gracePeriodAfter;
        if (Math.abs(seconds) <= allowed) return 0;
        const points = Math.round(Math.abs(seconds) - allowed) * pointsPerSecond;
        return maximumTimingPenalty >= 0 ? Math.min(maximumTimingPenalty, points) : points;
    };

    // Everything is drawn for a 76 px high scale and grows with it (a wide screen gets a taller one).
    const k = height / 76;
    const smallFont = 13 * k;
    // Vertical layout: the pointer's label, the pointer, the track, the values under it.
    const trackY = Math.round(height * 0.62);
    const valueY = trackY + 18 * k;
    const bandTop = trackY - 14 * k;

    // Penalty values along the track: from the end of the scale inwards by quarters, as before, skipping any that would
    // crowd the middle.
    const marks: number[] = [];
    for (let s = maximumSeconds; s > grace + 0.5; s /= 4) marks.push(s);
    const middleGap = 34 * k;
    const visibleMarks = marks.filter(s => secondsToX(s) - centre > middleGap);

    const offsetWithinGrace = crossingOffsetEstimate < 0
        ? -crossingOffsetEstimate <= gracePeriodBefore
        : crossingOffsetEstimate <= gracePeriodAfter;
    const pointerColour = missed ? "var(--hud-red)" : offsetWithinGrace ? "var(--hud-ok)" : "var(--hud-red)";
    const pointerX = secondsToX(crossingOffsetEstimate);
    const label = missed ? "Missed" : `${estimatedScore > 0 ? "+" : ""}${Math.round(estimatedScore)}`;
    const labelWidth = Math.max(40, label.length * 10 + 16) * k;

    if (width <= 0) return null;

    return (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
            aria-label={missed ? "Gate missed" : `${final ? "Crossed" : "Predicted"} ${Math.round(crossingOffsetEstimate)} seconds from the required time, ${Math.round(estimatedScore)} points`}
            style={{ display: "block", overflow: "visible", fontFamily: '"Barlow Condensed", "Barlow", sans-serif' }}>
            {/* The track, early to late. */}
            <line x1={SIDE_PADDING} x2={width - SIDE_PADDING} y1={trackY} y2={trackY} stroke="var(--hud-line)" strokeWidth={2 * k} strokeLinecap="round" />
            {/* The grace period: no penalty inside it. */}
            <rect x={secondsToX(-gracePeriodBefore)} y={bandTop} width={Math.max(2, secondsToX(gracePeriodAfter) - secondsToX(-gracePeriodBefore))} height={trackY - bandTop + 2}
                rx={3} fill="var(--hud-ok)" opacity={0.18} />
            <line x1={centre} x2={centre} y1={bandTop} y2={trackY + 4} stroke="var(--hud-ok)" strokeWidth={2 * k} />
            <text x={centre} y={valueY} textAnchor="middle" fontSize={smallFont} fontWeight={600} fill="var(--hud-ok)">On time</text>

            {visibleMarks.map(s => (
                <g key={s} fill="var(--hud-muted)" fontSize={smallFont} fontWeight={600}>
                    <line x1={secondsToX(-s)} x2={secondsToX(-s)} y1={trackY - 4 * k} y2={trackY + 4 * k} stroke="var(--hud-line)" strokeWidth={2 * k} />
                    <line x1={secondsToX(s)} x2={secondsToX(s)} y1={trackY - 4 * k} y2={trackY + 4 * k} stroke="var(--hud-line)" strokeWidth={2 * k} />
                    <text x={secondsToX(-s)} y={valueY} textAnchor="middle">{Math.ceil(secondsToPoints(-Math.floor(s)))}</text>
                    <text x={secondsToX(s)} y={valueY} textAnchor="middle">{Math.ceil(secondsToPoints(Math.ceil(s)))}</text>
                </g>
            ))}

            {/* Above the ends of the track, clear of the values under it. */}
            <text x={SIDE_PADDING} y={trackY - 8 * k} fontSize={smallFont} fontWeight={600} fill="var(--hud-muted)">Early</text>
            <text x={width - SIDE_PADDING} y={trackY - 8 * k} fontSize={smallFont} fontWeight={600} fill="var(--hud-muted)" textAnchor="end">Late</text>

            {/* The pointer and its points; it glides to each new estimate. */}
            <g style={{ transform: `translateX(${pointerX}px)`, transition: `transform ${POINTER_MOVE_MS}ms ease-out` }}>
                <rect x={-labelWidth / 2} y={2} width={labelWidth} height={24 * k} rx={6 * k}
                    fill={final || missed ? pointerColour : "var(--hud-surface)"} stroke={pointerColour} strokeWidth={2 * k} />
                <text x={0} y={2 + 18 * k} textAnchor="middle" fontSize={17 * k} fontWeight={700} fill={final || missed ? "var(--hud-surface)" : pointerColour}>{label}</text>
                <path d={`M ${-7 * k} ${bandTop - 6 * k} L ${7 * k} ${bandTop - 6 * k} L 0 ${trackY - 1} Z`} fill={pointerColour} />
            </g>
        </svg>
    );
};

export default GateScoreArrowRenderer;
