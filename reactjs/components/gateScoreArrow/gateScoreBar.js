import React, {Component} from "react";

export default class GateScoreBar extends Component {
    constructor(props) {
        super(props)
        this.context = context
    }

    drawBar(context) {
        const pixelsPerSecond = this.props.width / (this.props.maximumSeconds * 2)
        const gracePixelsBefore = pixelsPerSecond * this.props.graceSecondsBefore
        const gracePixelsAfter = pixelsPerSecond * this.props.graceSecondsAfter

        const middle = this.props.width / 2

        let earlyGradient = context.createLinearGradient(0, 0, middle - gracePixelsBefore, 0);
        earlyGradient.addColorStop(0, "red");
        earlyGradient.addColorStop(1, "white");
        context.fillStyle = earlyGradient;
        context.fillRect(0, 0, middle - gracePixelsAfter, this.props.height);

        let lateGradient = context.createLinearGradient(middle + gracePixelsAfter, 0, this.props.width, 0);
        lateGradient.addColorStop(1, "red");
        lateGradient.addColorStop(0, "white");
        context.fillStyle = lateGradient;
        context.fillRect(middle + gracePixelsAfter, 0, this.props.width, this.props.height);
    }

    componentDidUpdate(prevProps) {
        this.drawBar(this.context)
    }

    render() {
        return null
    }
}