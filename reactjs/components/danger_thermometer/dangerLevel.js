import React, {Component} from "react";
import {connect} from "react-redux";
import AirsportsThermometer from "./airsportsThermometer";
import AccumulatedScore from "./accumulatedScore";

const mapStateToProps = (state, props) => ({
    contestantTrack: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    dangerData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].danger_level : null,
    displayDangerLevel: state.displayDangerLevel
})

class ConnectedDangerLevel extends Component {
    render() {
        return <div style={{width: "29px"}}>
            {/*{this.props.dangerData && this.props.dangerData.danger_level === 100 ?*/}
            {/*    <AccumulatedScore value={this.props.dangerData.accumulated_score}/> : null}*/}
            <AccumulatedScore value={50}/>
            <AirsportsThermometer value={this.props.dangerData ? this.props.dangerData.danger_level : 0}/>
        </div>
    }
}

const
    DangerLevel = connect(mapStateToProps, {})(ConnectedDangerLevel)
export default DangerLevel