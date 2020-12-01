import React, {Component} from "react";
import {connect} from "react-redux";
import {pz} from "../utilities";
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";
import {displayOnlyContestantTrack, setDisplay} from "../actions";

var moment = require("moment");
var momentDurationFormatSetup = require("moment-duration-format");

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null
})

function getTrackingStateBackgroundClass(state) {
    if (["Tracking", "Procedure turn"].includes(state)) return "greenBackground";
    if (["Backtracking", "Failed procedure turn"].includes(state)) return "redBackground"
    return ""
}

class ConnectedAbbreviatedRank extends Component {
    constructor(props) {
        super(props)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
    }

    handleContestantLinkClick(contestantId) {
        this.props.setDisplay({displayType: CONTESTANT_DETAILS_DISPLAY, contestantId: contestantId})
        this.props.displayOnlyContestantTrack(contestantId)
    }


    render() {
        if (!this.props.contestantData) {
            return <div/>
        }
        return <tr
            key={"leaderboard" + this.props.contestantNumber}>
            <td style={{"backgroundColor": this.props.colour}}>&nbsp;</td>
            <td>{this.props.rank}</td>
            <td><a href={"#"}
                   onClick={() => this.handleContestantLinkClick(this.props.contestantId)}>{pz(this.props.contestantNumber, 2)} {this.props.contestantName}</a>
            </td>
            <td>{this.props.contestantData.score}</td>
            <td className={getTrackingStateBackgroundClass(this.props.contestantData.current_state)}>{this.props.contestantData.current_state}</td>
            <td>{this.props.contestantData.last_gate}</td>
            <td>{moment.duration(this.props.contestantData.last_gate_time_offset, "seconds").format()}</td>
            {/*<td>{d.lastGateTimeDifference}</td>*/}
        </tr>;
    }
}

const AbbreviatedRank = connect(mapStateToProps, {setDisplay, displayOnlyContestantTrack})(ConnectedAbbreviatedRank)
export default AbbreviatedRank