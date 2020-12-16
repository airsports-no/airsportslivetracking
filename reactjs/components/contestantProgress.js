import React, {Component} from "react";


export class ProjectedScore extends Component {
    render() {
        return <div>{(100 * this.props.score / this.props.progress).toFixed(0)}</div>
    }
}