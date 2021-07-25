import React, {Component} from "react";
import {connect} from "react-redux";

const {formatTime} = require("../utilities");
const mapStateToProps = (state, props) => ({
    latestPositionTime: props.contestantId ? state.contestantData[props.contestantId].latest_position_time : null,
    finished: props.contestantId ? state.contestantData[props.contestantId].calculator_finished || state.contestantData[props.contestantId].current_state === "Finished" : false,
    currentTime: state.currentTime
})

class ConnectedTimeDisplay extends Component {
    render() {
        if (this.props.latestPositionTime && !this.props.finished) {
            return <div className={this.props.class}>{formatTime(this.props.latestPositionTime)}</div>
        }
        return <div className={this.props.class}>{this.props.currentTime}</div>
    }
}

const TimeDisplay = connect(mapStateToProps, {})(ConnectedTimeDisplay)
export default TimeDisplay