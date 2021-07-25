import React, {Component} from "react";
import {connect} from "react-redux";

const {formatTime} = require("../utilities");
const mapStateToProps = (state, props) => ({
    latestPositionTime: state.contestantData[props.contestantId].latest_position_time
})

class ConnectedTimeDisplay extends Component {
    render() {
        if (this.props.latestPositionTime) {
            return <div className={this.props.class}>{formatTime(this.props.latestPositionTime)}</div>
        }
    }
}

const TimeDisplay = connect(mapStateToProps, {})(ConnectedTimeDisplay)
export default TimeDisplay