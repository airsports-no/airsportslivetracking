import React, { useRef, useEffect } from "react";

const ARROW_HEIGHT = 92, HORIZONTAL_LINE_THICKNESS = 3, VERTICAL_LINE_LENGTH = 10, NUMBER_PADDING = 5, PADDING = 36,
    ARROW_ICON_WIDTH = 70, BELOW_LINE_TEXT_POSITION = 75, BELOW_LINE_TEXT_X_OFFSET = 20, ANIMATION_STEPS = 10,
    ANIMATION_TIME = 1000, ARROW_TOP_OFFSET = 0, TOP_OFFSET = 42
const ARROW_ICON_HEIGHT = ARROW_ICON_WIDTH * 1.3

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
blackImage.src = document.configuration.STATIC_FILE_LOCATION + 'img/gate_score_arrow_black.gif';
const redImage = new Image();
redImage.src = document.configuration.STATIC_FILE_LOCATION + 'img/gate_score_arrow_red.gif';

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
        context.fillText(string, x - context.measureText(string).width / 2, ARROW_HEIGHT + length + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING);
    };

    const drawGracePeriod = (context: CanvasRenderingContext2D) => {
        context.fillStyle = "#92d468";
        const x = secondsToPosition(-gracePeriodBefore);
        const graceWidth = secondsToPosition(gracePeriodAfter) - x;
        context.fillRect(x - 1, TOP_OFFSET, graceWidth + 2, ARROW_ICON_HEIGHT - TOP_OFFSET + 1);
    };

    const drawNumberLine = (context: CanvasRenderingContext2D) => {
        const maximumSeconds = Math.max(gracePeriodAfter, gracePeriodBefore) + Math.ceil(maximumTimingPenalty / pointsPerSecond);
        // Mainline
        context.fillStyle = "#000000";
        context.fillRect(PADDING, ARROW_HEIGHT, width - PADDING * 2, HORIZONTAL_LINE_THICKNESS);
        drawGracePeriod(context);
        context.font = "10pt Verdana";
        context.fillStyle = "#262626";
        const textSize = context.measureText("PENALTY");
        const penaltytext = secondsToPosition(0) - textSize.width / 2;
        context.fillText("PENALTY", penaltytext, ARROW_HEIGHT + VERTICAL_LINE_LENGTH + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING);
        for (let i = maximumSeconds; i > Math.max(gracePeriodAfter, gracePeriodBefore); i /= 4) {
            const leftPosition = secondsToPosition(-i);
            const rightPosition = secondsToPosition(i);
            if (leftPosition > penaltytext - 5 || rightPosition < penaltytext + textSize.width + 5) {
                continue;
            }
            drawNumberAtPosition(context, leftPosition, secondsToPoints(Math.floor(-i)), VERTICAL_LINE_LENGTH);
            drawNumberAtPosition(context, rightPosition, secondsToPoints(Math.ceil(i)), VERTICAL_LINE_LENGTH);
        }
    };

    const drawRerenderedBackground = (context: CanvasRenderingContext2D) => {
        context.font = "16pt Verdana";
        context.fillStyle = "#a6a6a6";
        context.fillText("EARLY", PADDING + BELOW_LINE_TEXT_X_OFFSET, BELOW_LINE_TEXT_POSITION);
        const latex = width - context.measureText("Late").width - PADDING - BELOW_LINE_TEXT_X_OFFSET;
        context.fillText("LATE", latex, BELOW_LINE_TEXT_POSITION);
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
            context.clearRect(previousArrowPositionRef.current - ARROW_ICON_WIDTH / 2, 0, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT);
        }
        previousArrowPositionRef.current = x;
        drawRerenderedBackground(context);
        context.fillStyle = "#FFFFFF";
        context.drawImage(imageObj, start, ARROW_TOP_OFFSET, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT);
        context.font = "bold 18pt Verdana";
        let string = "" + Math.round(value);
        if (missed) {
            context.font = "bold 13pt Verdana";
            string = "MISS";
        }
        context.fillText(string, x - context.measureText(string).width / 2, 45 + ARROW_TOP_OFFSET);
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
        <div className="mt-[-42px]">
            <canvas id="myCanvas" ref={canvasRef} width={width} height={height} />
        </div>
    );
};

export default GateScoreArrowRenderer;