import React, {Component} from "react";
import {connect} from "react-redux";

const {formatTime} = require("../utilities");
const mapStateToProps = (state, props) => ({
    latestPositionTime: props.contestantId ? state.contestantData[props.contestantId].latest_position_time : null,
    finished: props.contestantId && (state.contestantData[props.contestantId].calculator_finished || state.contestantData[props.contestantId].current_state === "Finished"),
    currentTime: state.currentTime
})

class ConnectedTimeDisplay extends Component {
    constructor(props) {
        super(props)
        this.state = {contestantTime: null}
        this.timer = null

    }

    incrementTime() {
        if (this.state.contestantTime) {
            this.setState({contestantTime: new Date(this.state.contestantTime.getTime() + 1000)})
        }
        this.timer = setTimeout(() => this.incrementTime(), 1000)
    }

    updateTime() {
        this.setState({contestantTime: this.props.latestPositionTime})
        if (this.timer) {
            clearTimeout(this.timer)
        }
        this.timer = setTimeout(() => this.incrementTime(), 1000)
    }

    componentDidMount() {
        this.updateTime()
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.latestPositionTime !== prevProps.latestPositionTime && this.props.latestPositionTime) {
            this.updateTime()
        }
    }

    render() {
        return <div
            className={this.props.class}>{this.props.latestPositionTime && !this.props.finished ? formatTime(this.state.contestantTime) : this.props.currentTime}</div>
    }
}

const TimeDisplay = connect(mapStateToProps, {})(ConnectedTimeDisplay)
export default TimeDisplay