import React, {Component} from "react";
import {connect} from "react-redux";
import AirsportsThermometer from "./airsportsThermometer";
import AccumulatedScore from "./accumulatedScore";

const mapStateToProps = (state, props) => ({
    contestantTrack: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    dangerData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].danger_level : null,
    displayDangerLevel: state.displayDangerLevel
})
const GATE_FREEZE_TIME = 10

class ConnectedDangerLevel extends Component {
    constructor(props) {
        super(props)
        this.state = {
            currentDangerData: this.props.dangerData,
            frozenTime: null
        }
        this.restoreTimer = null
    }

    componentWillUnmount() {
        clearTimeout(this.restoreTimer)
    }

    componentDidUpdate(prevProps) {
        let frozen = this.state.frozenTime && new Date().getTime() - this.state.frozenTime.getTime() < GATE_FREEZE_TIME * 1000
        if (this.props.dangerData && prevProps.dangerData && this.props.dangerData.accumulated_score === 0 && this.state.currentDangerData.accumulated_score !== 0 && !this.state.frozenTime) {
            this.setState({frozenTime: new Date()})
            frozen = true
            // }), (GATE_FREEZE_TIME + 1) * 1000)
        }
        if ((!frozen && this.props.dangerData !== this.state.currentDangerData) || (frozen && this.props.dangerData.accumulated_score !== 0)) {
            clearTimeout(this.restoreTimer)
            this.setState({currentDangerData: this.props.dangerData, frozenTime: null})
        }
    }

    render() {
        return <div style={{width: "29px"}}>
            {this.state.currentDangerData && this.state.currentDangerData.danger_level === 100 ?
                <AccumulatedScore value={this.state.currentDangerData.accumulated_score}
                                  frozen={this.state.frozenTime != null}/> : null}
            <AirsportsThermometer value={this.props.dangerData ? this.props.dangerData.danger_level : 0}/>
        </div>
    }
}

const
    DangerLevel = connect(mapStateToProps, {})(ConnectedDangerLevel)
export default DangerLevel