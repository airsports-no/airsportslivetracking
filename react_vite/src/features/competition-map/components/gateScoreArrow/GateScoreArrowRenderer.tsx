import React, { useRef, useEffect } from "react";
import blackImageSrc from './gate_score_arrow_black.gif';
import redImageSrc from './gate_score_arrow_red.gif';

const HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW = 55, HORIZONTAL_LINE_THICKNESS = 3, NUMBER_PADDING = 12, PADDING = 36,
    ARROW_ICON_HEIGHT = 50,  BELOW_LINE_TEXT_X_OFFSET = 20, ANIMATION_STEPS = 10,
    ANIMATION_TIME = 1000,  TOP_OFFSET = 0
const ARROW_ICON_WIDTH = ARROW_ICON_HEIGHT / 1.3

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

const blackImage = new Image();
blackImage.src = blackImageSrc;
const redImage = new Image();
redImage.src = redImageSrc;

const GateScoreArrowRenderer: React.FC<GateScoreArrowRendererProps> = ({
    width,
    height,
    pointsPerSecond,
    maximumTimingPenalty,
    gracePeriodBefore,
    gracePeriodAfter,
    crossingOffsetEstimate,
    estimatedScore,
    contestantId,
    final,
    missed,
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const animationTimerRef = useRef<number | null>(null);
    const animationStepNumberRef = useRef(0);
    const previousArrowPositionRef = useRef<number | null>(null);
    const previousSecondsRef = useRef(0);
    const minXRef = useRef(0);
    const maxXRef = useRef(0);

    // Helper functions (converted from class methods)
    const secondsToPosition = (seconds: number) => {
        const maximumSeconds = Math.max(gracePeriodAfter, gracePeriodBefore) + maximumTimingPenalty / pointsPerSecond;
        const sideLength = (width / 2) - PADDING;
        const offset = sideLength / Math.log10(maximumSeconds);
        if (seconds <= 0) {
            return width / 2 - Math.log10(-seconds + 1) * offset;
        } else {
            return width / 2 + Math.log10(seconds + 1) * offset;
        }
    };

    const secondsToPoints = (seconds: number) => {
        let grace;
        if (seconds < 0) {
            grace = gracePeriodBefore;
        } else {
            grace = gracePeriodAfter;
        }
        if ((seconds < 0 && seconds >= -gracePeriodBefore) || (seconds >= 0 && seconds <= gracePeriodAfter)) {
            return 0;
        } else {
            let score = Math.round((Math.abs(seconds)) - grace) * pointsPerSecond;
            if (maximumTimingPenalty >= 0) {
                score = Math.min(maximumTimingPenalty, score);
            }
            return score;
        }
    };

    const drawNumberAtPosition = (context: CanvasRenderingContext2D, x: number, value: number, length: number) => {
        context.fillStyle = "#a6a6a6";
        context.font = "10pt Verdana";
        const string = "" + Math.ceil(value);
        context.fillText(string, x - context.measureText(string).width / 2, height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING);
    };

    const drawGracePeriod = (context: CanvasRenderingContext2D) => {
        context.fillStyle = "#92d468";
        const x = secondsToPosition(-gracePeriodBefore);
        const graceWidth = secondsToPosition(gracePeriodAfter) - x;
        context.fillRect(x - 1, TOP_OFFSET, graceWidth + 2, height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW - HORIZONTAL_LINE_THICKNESS);
    };

    const drawNumberLine = (context: CanvasRenderingContext2D) => {
        const maximumSeconds = Math.max(gracePeriodAfter, gracePeriodBefore) + Math.ceil(maximumTimingPenalty / pointsPerSecond);
        // Mainline
        context.fillStyle = "#000000";
        context.fillRect(PADDING, height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW, width - PADDING * 2, HORIZONTAL_LINE_THICKNESS);
        drawGracePeriod(context);
        context.font = "10pt Verdana";
        context.fillStyle = "#262626";
        const textSize = context.measureText("PENALTY");
        const penaltytext = secondsToPosition(0) - textSize.width / 2;
        context.fillText("PENALTY", penaltytext, height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING);
        for (let i = maximumSeconds; i > Math.max(gracePeriodAfter, gracePeriodBefore); i /= 4) {
            const leftPosition = secondsToPosition(-i);
            const rightPosition = secondsToPosition(i);
            if (leftPosition > penaltytext - 5 || rightPosition < penaltytext + textSize.width + 5) {
                continue;
            }
            drawNumberAtPosition(context, leftPosition, secondsToPoints(Math.floor(-i)), 0);
            drawNumberAtPosition(context, rightPosition, secondsToPoints(Math.ceil(i)), 0);
        }
    };

    const drawRerenderedBackground = (context: CanvasRenderingContext2D) => {
        context.font = "16pt Verdana";
        context.fillStyle = "#a6a6a6";
        const y= height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW - 10;
        context.fillText("EARLY", PADDING + BELOW_LINE_TEXT_X_OFFSET, y);
        const latex = width - context.measureText("Late").width - PADDING - BELOW_LINE_TEXT_X_OFFSET;
        context.fillText("LATE", latex, y);
        drawGracePeriod(context);
    };

    const drawArrow = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext("2d");
        if (!context) return;

        const animationStep = (secondsToPosition(crossingOffsetEstimate) - secondsToPosition(previousSecondsRef.current)) / ANIMATION_STEPS;
        let x: number;
        let value: number;

        if (animationStepNumberRef.current === ANIMATION_STEPS || final) {
            x = Math.min(maxXRef.current, Math.max(minXRef.current, secondsToPosition(crossingOffsetEstimate)));
            if (animationTimerRef.current) clearInterval(animationTimerRef.current);
            animationTimerRef.current = null;
        } else {
            x = Math.min(maxXRef.current, Math.max(minXRef.current, secondsToPosition(previousSecondsRef.current) + animationStepNumberRef.current * animationStep));
            animationStepNumberRef.current++;
        }
        value = estimatedScore;
        const start = x - ARROW_ICON_WIDTH / 2;
        let imageObj = blackImage;
        if (final) {
            imageObj = redImage;
        }
        if (previousArrowPositionRef.current !== null) {
            context.clearRect(previousArrowPositionRef.current - ARROW_ICON_WIDTH / 2, 0, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT+4);
        }
        const arrowY=height-HORIZONTAL_LINE_Y_OFFSET_FROM_BELOW - ARROW_ICON_HEIGHT
        previousArrowPositionRef.current = x;
        drawRerenderedBackground(context);
        context.fillStyle = "#FFFFFF";
        context.drawImage(imageObj, start, arrowY, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT);
        context.font = "bold 12pt Verdana";
        let string = "" + Math.round(value);
        if (missed) {
            context.font = "bold 13pt Verdana";
            string = "MISS";
        }
        context.fillText(string, x - context.measureText(string).width / 2, arrowY+25);
    };

    const drawEverything = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext("2d");
        if (!context) return;
        context.clearRect(0, 0, width, height); // Clear whole canvas before redrawing background
        const maximumSeconds = Math.max(gracePeriodAfter, gracePeriodBefore) + maximumTimingPenalty / pointsPerSecond;
        maxXRef.current = secondsToPosition(maximumSeconds);
        minXRef.current = secondsToPosition(-maximumSeconds);
        drawNumberLine(context);
        drawArrow();
    };

    const prevPropsRef = useRef({ crossingOffsetEstimate, final, missed, width, height, contestantId });

    // componentDidMount equivalent and prop changes for redrawing static elements
    useEffect(() => {
        animationStepNumberRef.current = ANIMATION_STEPS;
        drawEverything();

        return () => {
            if (animationTimerRef.current) clearInterval(animationTimerRef.current);
            animationTimerRef.current = null;
        };
    }, [contestantId, width, height, pointsPerSecond, maximumTimingPenalty, gracePeriodBefore, gracePeriodAfter]);

    // componentDidUpdate equivalent for animation/prop changes
    useEffect(() => {
        const prevCrossingOffsetEstimate = prevPropsRef.current.crossingOffsetEstimate;
        const prevFinal = prevPropsRef.current.final;
        const prevMissed = prevPropsRef.current.missed;
        const prevContestantId = prevPropsRef.current.contestantId;

        // Reset animation if contestantId or static drawing properties change
        if (contestantId !== prevContestantId || width !== prevPropsRef.current.width || height !== prevPropsRef.current.height) {
            if (animationTimerRef.current) clearInterval(animationTimerRef.current);
            animationTimerRef.current = null;
            animationStepNumberRef.current = ANIMATION_STEPS; // Ensures next drawEverything does a full render
            previousArrowPositionRef.current = null; // Reset arrow position
            previousSecondsRef.current = crossingOffsetEstimate; // Set initial previousSeconds for smooth animation start
            drawEverything(); // Full redraw for new contestant/size
        }


        if (crossingOffsetEstimate !== prevCrossingOffsetEstimate || final !== prevFinal || missed !== prevMissed) {
            if (animationTimerRef.current) clearInterval(animationTimerRef.current);
            animationTimerRef.current = null;
            animationStepNumberRef.current = 0; // Start animation from step 0
            previousSecondsRef.current = prevCrossingOffsetEstimate; // Store the actual previous estimate

            drawArrow(); // Draw initial state before animation starts

            // Only animate if not final (final state should be immediate)
            if (!final) {
                animationTimerRef.current = window.setInterval(() => {
                    if (animationStepNumberRef.current < ANIMATION_STEPS) {
                        drawArrow();
                    } else {
                        if (animationTimerRef.current) clearInterval(animationTimerRef.current);
                        animationTimerRef.current = null;
                    }
                }, ANIMATION_TIME / ANIMATION_STEPS);
            }
        }
        
        // Update previous props for the next render cycle
        prevPropsRef.current = { crossingOffsetEstimate, final, missed, width, height, contestantId };

    }, [
        crossingOffsetEstimate, estimatedScore, final, missed, contestantId, width, height, // Add width, height, contestantId here too for changes that trigger animation context
        pointsPerSecond, maximumTimingPenalty, gracePeriodBefore, gracePeriodAfter, drawArrow, drawEverything // Dependencies for useCallback functions
    ]);


    return (
        <div className="">
            <canvas id="myCanvas" ref={canvasRef} width={width} height={height} />
        </div>
    );
};

export default GateScoreArrowRenderer;