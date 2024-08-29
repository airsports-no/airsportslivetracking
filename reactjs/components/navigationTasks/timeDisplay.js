import React, { Component } from "react";
import { connect } from "react-redux";
import moment from 'moment';
var momentTimeZone = require("moment-timezone");


const mapStateToProps = (state, props) => ({
    navigationTaskTimezone: state.navigationTask.time_zone,
    calculationDelayMinutes: state.navigationTask.calculation_delay_minutes
})

class ConnectedTimeDisplay extends Component {
    constructor(props) {
        super(props)
        this.state = { currentTime: null }
        this.timer = null

    }

    incrementTime() {
        if (this.props.calculationDelayMinutes !== undefined) {
            this.setState({ currentTime: moment().subtract(this.props.calculationDelayMinutes, 'minutes').tz(this.props.navigationTaskTimezone).format('HH:mm:ss') })
        }
        this.timer = setTimeout(() => this.incrementTime(), 1000)
    }



    componentDidMount() {
        this.incrementTime()
    }



    render() {
        return <div
            className={this.props.class}>{this.state.currentTime}</div>
    }
}

const TimeDisplay = connect(mapStateToProps, {})(ConnectedTimeDisplay)
export default TimeDisplay