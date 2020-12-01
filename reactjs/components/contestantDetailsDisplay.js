import React, {Component} from "react";
import {connect} from "react-redux";
import {contestantShortForm} from "../utilities";

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
})

class ConnectedContestantDetailsDisplay extends Component {
    render() {
        if (!this.props.contestantData) {
            return <div/>
        }
        const events = this.props.contestantData.score_log.map((line, index) => {
            return <li key={this.props.contestantData.contestant.contestant_number + "event" + index}>{line}</li>
        })
        return <div><h2>{contestantShortForm(this.props.contestantData.contestant)}</h2>
            <ol>
                {events}
            </ol>
        </div>

    }
}

const ContestantDetailsDisplay = connect(mapStateToProps)(ConnectedContestantDetailsDisplay)
export default ContestantDetailsDisplay