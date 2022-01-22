import React, {Component} from "react";
import {connect} from "react-redux";
import GateScoreArrowRenderer from "./gateScoreArrowRenderer";
import GateCountdownTimer from "./gateCountdownTimer";
import './gateScore.css'

const mapStateToProps = (state, props) => ({
    contestantTrack: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    arrowData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].gate_distance_and_estimate : null,
    scorecard: state.navigationTask.scorecard,
    waypoints: state.navigationTask.route.waypoints,
    displayGateArrow: state.displayGateArrow
})

const GATE_FREEZE_TIME = 15

class ConnectedGateScoreArrow extends Component {
    constructor(props) {
        super(props)
        this.state = {
            currentArrowData: this.props.arrowData,
            finished: {}
        }
        this.frozenTime = null
    }

    componentDidMount() {
    }

    getWaypointType(waypointName) {
        return this.props.waypoints.find((waypoint) => {
            return waypoint.name === waypointName
        }).type
    }

    getRule(ruleName) {
        const waypointType = this.getWaypointType(this.state.currentArrowData.waypoint_name)
        const gateScore = this.props.scorecard.gatescore_set.find((gate) => {
            return gate.gate_type === waypointType
        })
        return gateScore[ruleName]
    }

    getGracePeriodBefore() {
        return this.getRule("graceperiod_before")
    }

    getGracePeriodAfter() {
        return this.getRule("graceperiod_after")
    }

    getPointsPerSecond() {
        return this.getRule("penalty_per_second")
    }

    getMissedPenalty() {
        return this.getRule("missed_penalty")
    }


    getMaximumTimingPenalty() {
        return this.getRule("maximum_penalty")
    }


    componentDidUpdate(prevProps) {
        const frozen = this.frozenTime && new Date().getTime() - this.frozenTime.getTime() < GATE_FREEZE_TIME * 1000
        if (this.props.arrowData && (this.props.arrowData.missed || this.props.arrowData.final)) {
            // Gate change, delay
            if (!this.frozenTime) {
                this.frozenTime = new Date()
                this.setState({currentArrowData: this.props.arrowData})
            }
        }
        if (!frozen && this.props.arrowData !== this.state.currentArrowData || this.props.contestantId!==prevProps.contestantId) {
            this.frozenTime = null
            this.setState({currentArrowData: this.props.arrowData})
        }
        if (!this.state.finished[this.props.contestantId] && this.props.contestantTrack && this.props.contestantTrack.passed_finish_gate) {
            setTimeout(() => {
                this.setState({finished: {...this.state.finished, [this.props.contestantId]: true}})
            }, GATE_FREEZE_TIME * 1000)
        }
    }


    render() {
        if (this.state.currentArrowData && !this.state.finished[this.props.contestantId] && this.props.displayGateArrow) {
            return <div className={"gate-score-arrow"}>
                <div className={"gate-score-next-gate row col-12"}>
                    NEXT GATE: {this.state.currentArrowData.waypoint_name}
                </div>
                <div className={"row gate-arrow-shadow"}>
                    <div className={"col-2"}>
                        <GateCountdownTimer
                            secondsToPlannedCrossing={this.state.currentArrowData.seconds_to_planned_crossing}
                            crossingOffsetEstimate={this.state.currentArrowData.estimated_crossing_offset}/>
                    </div>
                    <div className={"col-10"}>
                        <GateScoreArrowRenderer width={this.props.width} height={this.props.height}
                                                pointsPerSecond={this.getPointsPerSecond()}
                                                maximumTimingPenalty={this.getMaximumTimingPenalty()}
                                                gracePeriodBefore={this.getGracePeriodBefore()}
                                                gracePeriodAfter={this.getGracePeriodAfter()}
                            // missedPenalty={this.getMissedPenalty()}
                            //                     secondsToPlannedCrossing={this.state.currentArrowData.seconds_to_planned_crossing}
                            crossingOffsetEstimate={this.state.currentArrowData.estimated_crossing_offset}
                                                estimatedScore={this.state.currentArrowData.estimated_score}
                            // waypointName={this.state.currentArrowData.waypoint_name}
                                                contestantId={this.props.contestantId}
                                                final={this.state.currentArrowData.final}
                                                missed={this.state.currentArrowData.missed}/>
                    </div>
                </div>
            </div>
        }
        return null
    }
}

const
    GateScoreArrow = connect(mapStateToProps, {})(ConnectedGateScoreArrow)
export default GateScoreArrow