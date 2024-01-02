import React, {Component} from "react";
const ARROW_HEIGHT = 92, HORIZONTAL_LINE_THICKNESS = 3, VERTICAL_LINE_LENGTH = 10, NUMBER_PADDING = 5, PADDING = 36,
    ARROW_ICON_WIDTH = 70, BELOW_LINE_TEXT_POSITION = 75, BELOW_LINE_TEXT_X_OFFSET = 20, ANIMATION_STEPS = 10,
    ANIMATION_TIME = 1000, ARROW_TOP_OFFSET = 0, TOP_OFFSET = 42
const ARROW_ICON_HEIGHT = ARROW_ICON_WIDTH * 1.3

const blackImage = new Image()
blackImage.src = '/static/img/gate_score_arrow_black.gif';
const redImage = new Image()
redImage.src = '/static/img/gate_score_arrow_red.gif';

export default class GateScoreArrowRenderer extends Component {
    constructor(props) {
        super(props)
        this.animationTimer = null
        this.animationStepNumber = 0
        this.previousArrowPosition = null
        this.previousSeconds = 0
        this.previousPosition = 999999
        this.minX = 0
        this.maxX = 0
        this.drawArrow.bind(this)
    }

    drawEverything() {
        this.drawArrow()
    }

    drawBackground() {
        const canvas = document.getElementById("myCanvas");
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, this.props.width, this.props.height)
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        this.maxX = this.secondsToPosition(maximumSeconds)
        this.minX = this.secondsToPosition(-maximumSeconds)
        this.drawNumberLine(context)
    }

    componentDidMount() {
        clearInterval(this.animationTimer)
        this.animationStepNumber = ANIMATION_STEPS
        this.drawBackground()
        this.drawEverything()
    }

    componentWillUnmount() {
        clearInterval(this.animationTimer)
    }

    drawArrow() {
        const canvas = document.getElementById("myCanvas");
        const context = canvas.getContext("2d");
        const animationStep = (this.secondsToPosition(this.props.crossingOffsetEstimate) - this.secondsToPosition(this.previousSeconds)) / ANIMATION_STEPS
        let x, value
        if (this.animationStepNumber === ANIMATION_STEPS || this.props.final) {
            x = Math.min(this.maxX, Math.max(this.minX, this.secondsToPosition(this.props.crossingOffsetEstimate)))
            clearInterval(this.animationTimer)
        } else {
            x = Math.min(this.maxX, Math.max(this.minX, this.secondsToPosition(this.previousSeconds) + this.animationStepNumber * animationStep))
            this.animationStepNumber++
        }
        value = this.props.estimatedScore
        const start = x - ARROW_ICON_WIDTH / 2
        let imageObj = blackImage
        if (this.props.final) {
            imageObj = redImage
        }
        if (this.previousArrowPosition) {
            context.clearRect(this.previousArrowPosition - ARROW_ICON_WIDTH / 2, 0, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT)
        }
        this.previousArrowPosition = x
        this.drawRerenderedBackground(context)
        context.fillStyle = "#FFFFFF"
        context.drawImage(imageObj, start, ARROW_TOP_OFFSET, ARROW_ICON_WIDTH, ARROW_ICON_HEIGHT)
        context.font = "bold 18pt Verdana";
        let string = "" + Math.round(value)
        if (this.props.missed) {
            context.font = "bold 13pt Verdana";
            string = "MISS"
        }
        context.fillText(string, x - context.measureText(string).width / 2, 45 + ARROW_TOP_OFFSET)
    }

    drawNumberAtPosition(context, x, value, length) {
        context.fillStyle = "#a6a6a6"
        context.font = "10pt Verdana";
        const string = "" + Math.ceil(value)
        context.fillText(string, x - context.measureText(string).width / 2, ARROW_HEIGHT + length + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING)
    }

    secondsToPosition(seconds) {
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + this.props.maximumTimingPenalty / this.props.pointsPerSecond
        const sideLength = (this.props.width / 2) - PADDING
        const offset = sideLength / Math.log10(maximumSeconds)
        if (seconds <= 0) {
            return this.props.width / 2 - Math.log10(-seconds + 1) * offset
        } else {
            return this.props.width / 2 + Math.log10(seconds + 1) * offset
        }
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
        const maximumSeconds = Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore) + Math.ceil(this.props.maximumTimingPenalty / this.props.pointsPerSecond)
        // Mainline
        context.fillStyle = "#000000";
        context.fillRect(PADDING, ARROW_HEIGHT, this.props.width - PADDING * 2, HORIZONTAL_LINE_THICKNESS);
        this.drawGracePeriod(context)
        context.font = "10pt Verdana";
        context.fillStyle = "#262626"
        const textSize = context.measureText("PENALTY")
        const penaltytext = this.secondsToPosition(0) - textSize.width / 2
        context.fillText("PENALTY", penaltytext, ARROW_HEIGHT + VERTICAL_LINE_LENGTH + HORIZONTAL_LINE_THICKNESS + NUMBER_PADDING)
        for (let i = maximumSeconds; i > Math.max(this.props.gracePeriodAfter, this.props.gracePeriodBefore); i /= 4) {
            const leftPosition = this.secondsToPosition(-i)
            const rightPosition = this.secondsToPosition(i)
            if (leftPosition > penaltytext - 5 || rightPosition < penaltytext + textSize.width + 5) {
                continue
            }
            this.drawNumberAtPosition(context, leftPosition, this.secondsToPoints(Math.floor(-i)), VERTICAL_LINE_LENGTH)
            this.drawNumberAtPosition(context, rightPosition, this.secondsToPoints(Math.ceil(i)), VERTICAL_LINE_LENGTH)
        }
    }

    drawRerenderedBackground(context) {
        context.font = "16pt Verdana";
        context.fillStyle = "#a6a6a6"
        context.fillText("EARLY", PADDING + BELOW_LINE_TEXT_X_OFFSET, BELOW_LINE_TEXT_POSITION)
        const latex = this.props.width - context.measureText("Late").width - PADDING - BELOW_LINE_TEXT_X_OFFSET
        context.fillText("LATE", latex, BELOW_LINE_TEXT_POSITION)
        this.drawGracePeriod(context)
    }

    drawGracePeriod(context) {
        context.fillStyle = "#92d468";
        const x = this.secondsToPosition(-this.props.gracePeriodBefore)
        const width = this.secondsToPosition(this.props.gracePeriodAfter) - x
        context.fillRect(x - 1, TOP_OFFSET, width + 2, ARROW_ICON_HEIGHT - TOP_OFFSET + 1);
    }


    componentDidUpdate(prevProps) {
        if (this.props.width !== prevProps.width || ((this.props.contestantId !== prevProps.contestantId || this.props.waypointName !== prevProps.waypointName) && this.props.waypointName)) {
            clearInterval(this.animationTimer)
            this.animationStepNumber = ANIMATION_STEPS
            this.drawEverything()
        }

        if (this.props.crossingOffsetEstimate !== prevProps.crossingOffsetEstimate || this.props.final !== prevProps.final || this.props.missed !== prevProps.missed) {
            clearInterval(this.animationTimer)
            this.animationStepNumber = 0
            this.previousSeconds = prevProps.crossingOffsetEstimate
            this.drawEverything()
            this.animationTimer = setInterval(() => this.drawEverything(), ANIMATION_TIME / ANIMATION_STEPS)
        }
    }

    render() {
        return <div className={"gate-arrow-canvas"}>
            <canvas id="myCanvas" width={this.props.width} height={this.props.height}/>
        </div>
    }
}

