import React, {Component} from "react";
import Table from "react-bootstrap/Table";
import {pz} from "../utilities";
import {connect} from "react-redux";

const mapStateToProps = (state, props) => {
    let scores = [];
    if (state.contestantData !== undefined) {
        for (const contestantId in state.contestantData) {
            let value = state.contestantData[contestantId].contestant_track
            if (value) {
                if (value.score_per_gate.hasOwnProperty(props.turningPointName)) {
                    scores.push({
                        score: value.score_per_gate[props.turningPointName],
                        contestantId: contestantId,
                        contestantName: value.contestant.team.pilot,
                        contestantNumber: value.contestant.contestant_number
                    })
                }
            }
        }
    }
    return {turningPointScores: scores}
}


class ConnectedTurningPointDisplay extends Component {
    render() {
        let scores = this.props.turningPointScores.sort((a, b) => {
            if (a.score > b.score) return 1;
            if (a.score < b.score) return -1;
            return 0
        }).map((c, index) => {
            return <tr
                key={"turningpoint" + this.props.turningPointName + c.contestantNumber}>
                <td style={{"backgroundColor": this.props.colourMap[c.contestantId]}}>&nbsp;</td>
                <td>{index + 1}</td>
                <td>{pz(c.contestantNumber, 2)} {c.contestantName}</td>
                <td>{c.score}</td>
            </tr>
        })
        return <div><h2>{this.props.turningPointName}</h2>
            <Table bordered hover striped size={"sm"} responsive>
                <thead>
                <tr>
                    <td/>
                    <td>#</td>
                    <td>Team</td>
                    <td>Score</td>
                </tr>
                </thead>
                <tbody>{scores}</tbody>
            </Table>
        </div>

    }
}

const TurningPointDisplay = connect(mapStateToProps)(ConnectedTurningPointDisplay)
export default TurningPointDisplay