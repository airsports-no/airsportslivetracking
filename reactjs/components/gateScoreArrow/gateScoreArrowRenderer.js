import React, {Component} from "react";

const ARROW_HEIGHT = 60, HORIZONTAL_LINE_THICKNESS = 3, VERTICAL_LINE_LENGTH = 10, NUMBER_PADDING = 10, PADDING = 30,
    ARROW_ICON_WIDTH = 40, BELOW_LINE_TEXT_POSITION = 100, BELOW_LINE_TEXT_X_OFFSET = 20, ANIMATION_STEPS = 10,
    ANIMATION_TIME = 1000
const ARROW_ICON_HEIGHT = ARROW_ICON_WIDTH * 1.3

export default class GateScoreArrowRenderer extends Component {
    constructor(props) {
        super(props)
        this.animationTimer = null
        this.animationStepNumber = 0
        this.previousArrowPosition = null
        this.previousSeconds = 0
        this.drawArrow.bind(this)
    }

    drawBackground() {
        const canvas = document.getElementById("myCanvas");
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, this.props.width, this.props.height)
        // this.drawBar(context)
        this.drawBarLower(context)
        this.drawNumberLine(context)
    }

    componentDidMount() {
        clearInterval(this.animationTimer)
        this.drawBackground()
        this.animationStepNumber = ANIMATION_STEPS
        this.drawArrow()
    }

    componentWillUnmount() {
        clearInterval(this.animationTimer)
    }

    drawArrow() {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const canvas = document.getElementById("myCanvas");
        const context = canvas.getContext("2d");
        const animationStep = (this.props.seconds - this.previousSeconds) / ANIMATION_STEPS
        let x, value
        if (this.animationStepNumber === ANIMATION_STEPS || this.props.final) {
            x = this.secondsToPosition(Math.min(maximumSeconds, Math.max(-maximumSeconds, this.props.seconds)))
            value = this.secondsToPoints(this.props.seconds)
            clearInterval(this.animationTimer)
        } else {
            x = this.secondsToPosition(Math.min(maximumSeconds, Math.max(-maximumSeconds, this.previousSeconds + (this.animationStepNumber * animationStep))))
            value = this.secondsToPoints(this.previousSeconds + (this.animationStepNumber * animationStep))
            this.animationStepNumber++
        }
        // if (x === this.previousArrowPosition) {
        //     return
        // }
        const start = x - ARROW_ICON_WIDTH / 2
        const imageObj = new Image();
        imageObj.src = '/static/img/gate_score_arrow_black.gif';
        if (this.props.final) {
            imageObj.src = '/static/img/gate_score_arrow_white.gif';
        }
        imageObj.addEventListener('load', () => {
            if (this.previousArrowPosition) {
                context.clearRect(this.previousArrowPosition - ARROW_ICON_WIDTH / 2, 0, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT)
            }
            this.previousArrowPosition = x
            context.fillStyle = "#FFFFFF"
            if (this.props.final) {
                context.fillStyle = "#000000"
            }
            context.drawImage(imageObj, start, 0, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT)
            context.font = "bold 14pt Courier";
            let string = "" + Math.round(value)
            if (this.props.missed) {
                context.font = "bold 11pt Courier";
                string = "MISS"
            }
            context.fillText(string, x - context.measureText(string).width / 2, 27)
        })
    }

    drawNumberAtPosition(context, x, value, length) {
        context.fillStyle = "#000000";
        context.fillRect(x - 2, ARROW_HEIGHT - (length / 2) + HORIZONTAL_LINE_THICKNESS / 2, 2, HORIZONTAL_LINE_THICKNESS + length);
        const string = "" + Math.round(value)
        context.fillText(string, x - context.measureText(string).width / 2, ARROW_HEIGHT + length + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING)
    }

    secondsToPosition(seconds) {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const pixelsPerSecond = (this.props.width - PADDING * 2) / (maximumSeconds * 2)
        return PADDING + (maximumSeconds + seconds) * pixelsPerSecond
    }

    secondsToPoints(seconds) {
        let grace
        if (seconds < 0) {
            grace = this.props.gracePeriodBefore
        } else {
            grace = this.props.gracePeriodAfter
        }
        if (seconds < 0 && seconds >= -this.props.gracePeriodBefore || seconds >= 0 && seconds <= this.props.gracePeriodAfter) {
            return 0
        } else {
            let score = Math.round((Math.abs(seconds)) - grace) * this.props.pointsPerSecond
            if (this.props.maximumTimingPenalty >= 0) {
                score = Math.min(this.props.maximumTimingPenalty, score)
            }
            return score
        }
    }

    drawNumberLine(context) {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const pixelsPerSecond = (this.props.width - PADDING) / (maximumSeconds * 2)
        // Mainline
        context.fillStyle = "#000000";
        context.fillRect(PADDING, ARROW_HEIGHT, this.props.width - PADDING * 2, HORIZONTAL_LINE_THICKNESS);
        const steps = 6  // Must be Even
        const stepDistance = this.props.width / steps
        const stepDistanceSeconds = 2 * maximumSeconds / steps
        this.drawGracePeriod(context)
        context.font = "10pt Courier";
        for (let i = -steps / 2; i < 1 + steps / 2; i++) {
            this.drawNumberAtPosition(context, this.secondsToPosition(i * stepDistanceSeconds), this.secondsToPoints(i * stepDistanceSeconds), VERTICAL_LINE_LENGTH)
        }
        context.font = "bold 10pt Courier";
        context.fillText("Early", PADDING + BELOW_LINE_TEXT_X_OFFSET, BELOW_LINE_TEXT_POSITION)
        const latex = this.props.width - context.measureText("Late").width - PADDING - BELOW_LINE_TEXT_X_OFFSET
        context.fillText("Late", latex, BELOW_LINE_TEXT_POSITION)
        context.font = "bold 12pt Courier";
        const wpx = this.props.width / 2 - context.measureText(this.props.waypointName).width / 2
        context.fillText(this.props.waypointName, wpx, BELOW_LINE_TEXT_POSITION)
    }

    drawGracePeriod(context) {
        context.fillStyle = "#93ff9f";
        const x = this.secondsToPosition(-this.props.gracePeriodBefore)
        const width = this.secondsToPosition(this.props.gracePeriodAfter) - x
        context.fillRect(x - 1, ARROW_HEIGHT - (VERTICAL_LINE_LENGTH / 2) + HORIZONTAL_LINE_THICKNESS / 2, width, HORIZONTAL_LINE_THICKNESS + VERTICAL_LINE_LENGTH);
    }

    drawBar(context) {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const pixelsPerSecond = this.props.width / (maximumSeconds * 2)
        const gracePixelsBefore = pixelsPerSecond * this.props.gracePeriodBefore
        const gracePixelsAfter = pixelsPerSecond * this.props.gracePeriodAfter

        const middle = this.props.width / 2

        let earlyGradient = context.createLinearGradient(0, 0, middle, 0);
        earlyGradient.addColorStop(0, "rgba(0, 0, 0, 0.5)");
        earlyGradient.addColorStop(1, "rgba(255, 255, 255, 1.0)");

        // earlyGradient.addColorStop(0, "red");
        // earlyGradient.addColorStop(1, "white");
        context.fillStyle = earlyGradient;
        context.fillRect(0, 0, middle, this.props.height);

        let lateGradient = context.createLinearGradient(middle, 0, this.props.width, 0);
        lateGradient.addColorStop(1, "rgba(0, 0, 0, 0.5)");
        lateGradient.addColorStop(0, "rgba(255, 255, 255, 0.5)");
        // lateGradient.addColorStop(1, "red");
        // lateGradient.addColorStop(0, "white");
        context.fillStyle = lateGradient;
        context.fillRect(middle, 0, this.props.width, this.props.height);
    }

    drawBarLower(context) {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const pixelsPerSecond = this.props.width / (maximumSeconds * 2)

        const middle = this.props.width / 2
        let earlyGradient = context.createLinearGradient(0, 0, middle, 0);
        earlyGradient.addColorStop(0, "rgba(127, 127, 127, 0.5)");
        earlyGradient.addColorStop(1, "rgba(255, 255, 255, 0.5)");

        // earlyGradient.addColorStop(0, "red");
        // earlyGradient.addColorStop(1, "white");
        context.fillStyle = earlyGradient;
        context.fillRect(0, ARROW_HEIGHT - VERTICAL_LINE_LENGTH / 2, middle, this.props.height - ARROW_HEIGHT + VERTICAL_LINE_LENGTH);

        let lateGradient = context.createLinearGradient(middle, 0, this.props.width, 0);
        lateGradient.addColorStop(1, "rgba(127, 127, 127, 0.5)");
        lateGradient.addColorStop(0, "rgba(255, 255, 255, 0.5)");
        // lateGradient.addColorStop(1, "red");
        // lateGradient.addColorStop(0, "white");
        context.fillStyle = lateGradient;
        context.fillRect(middle, ARROW_HEIGHT - VERTICAL_LINE_LENGTH / 2, middle, this.props.height - ARROW_HEIGHT + VERTICAL_LINE_LENGTH);
    }

    componentDidUpdate(prevProps) {
        if (this.props.width !== prevProps.width || ((this.props.contestantId !== prevProps.contestantId || this.props.waypointName !== prevProps.waypointName) && this.props.waypointName)) {
            clearInterval(this.animationTimer)
            this.drawBackground()
            this.animationStepNumber = ANIMATION_STEPS
            this.drawArrow()
        }
        if (this.props.seconds !== prevProps.seconds || this.props.final !== prevProps.final || this.props.missed !== prevProps.missed) {
            clearInterval(this.animationTimer)
            this.previousSeconds = prevProps.seconds
            this.animationStepNumber = 0
            this.animationTimer = setInterval(() => this.drawArrow(), ANIMATION_TIME / ANIMATION_STEPS)
        }
    }

    render() {
        return <canvas id="myCanvas" width={this.props.width} height={this.props.height}/>
    }
}

