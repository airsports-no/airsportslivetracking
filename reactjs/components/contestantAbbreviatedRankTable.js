import React, {Component} from "react";
import {connect} from "react-redux";
import Table from "react-bootstrap/Table";
import {compareScore} from "../utilities";
import AbbreviatedRank from "./AbbreviatedRank";
import "bootstrap/dist/css/bootstrap.min.css"

const mapStateToProps = (state, props) => ({
    contestants: Object.keys(state.contestantData).map((key, index) => {
        return state.contestantData[key].contestant_track
    })
})


class ConnectedContestantAbbreviatedRankTable extends Component {
    render() {
        let contestants = this.props.contestants
        if (contestants.length === 0) {
            return <div/>
        }
        contestants = contestants.filter((contestant) => {
            return contestant && contestant.current_state !== "Waiting..."
        })
        contestants.sort(compareScore)
        const cm = this.props.colourMap
        const items = contestants.map((contestant, index) => {
            return <AbbreviatedRank key={"abbrev" + contestant.contestant.id} rank={index}
                                    contestantNumber={contestant.contestant.contestant_number}
                                    contestantName={contestant.contestant.team.pilot}
                                    contestantId={contestant.contestant.id}
                                    colour={cm[contestant.contestant.id]}/>
        })
        return <Table bordered hover striped size={"sm"} responsive>
            <thead>
            <tr>
                <td/>
                <td>#</td>
                <td>Team</td>
                <td>Score</td>
                <td>State</td>
                <td>Latest gate</td>
                <td>Time offset</td>
            </tr>
            </thead>
            <tbody>{items}</tbody>
        </Table>

    }
}

const ContestantAbbreviatedRankTable = connect(mapStateToProps)(ConnectedContestantAbbreviatedRankTable)
export default ContestantAbbreviatedRankTable