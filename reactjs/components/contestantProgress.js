import React, {Component} from "react";
import {buildStyles, CircularProgressbar} from "react-circular-progressbar";


export class ProjectedScore extends Component {
    render() {
        if (this.props.progress < 0.05) {
            return <div>{this.props.score}</div>
        }
        return <div>{(100 * this.props.score / this.props.progress).toFixed(0)}</div>
    }
}

export class ProgressCircle extends Component {
    render() {
        let trailColour = "#d6d6d6"
        let pathColour = "#3e98c7"
        const progress = this.props.progress;
        if (progress <= 0) {
            trailColour = "orange"
        } else if (progress <= 4) {
            trailColour = "#fff44f";
        } else {
            pathColour = "limegreen"
        }
        if (this.props.finished) {
            pathColour = "darkgreen"
        }
        return <CircularProgressbar className={"progressWheel"} value={progress}
                                    strokeWidth={50}
                                    styles={buildStyles({
                                        strokeLinecap: "butt",
                                        trailColor: trailColour,
                                        pathColor: pathColour
                                    })}
            //text={`${row.progress}`}
        />
    }
}