import React, {Component} from "react";
import {contestantShortForm} from "../utilities";
import {connect} from "react-redux";
import BootstrapTable from "react-bootstrap-table-next";
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";
import {displayOnlyContestantTrack, setDisplay, showLowerThirds} from "../actions";

const mapStateToProps = (state, props) => {
    let scores = [];
    if (state.contestantData !== undefined) {
        for (const contestantId in state.contestantData) {
            const contestant = state.contestants[contestantId]
            const initialLoading = state.initialLoadingContestantData[contestantId]
            const turning = state.contestantData[contestantId].gate_scores.find((gate) => {
                return gate.gate === props.turningPointName
            })
            if (turning) {
                scores.push({
                    colour: "",
                    score: initialLoading ? "Loading..." : turning.points,
                    contestantId: contestantId,
                    contestantName: contestantShortForm(contestant),
                    contestantNumber: contestant.contestant_number
                })
            }
        }
    }
    return {turningPointScores: scores}
}


class ConnectedTurningPointDisplay extends Component {
    constructor(props) {
        super(props);
        this.numberStyle = this.numberStyle.bind(this)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
    }


    getColour(contestantNumber) {
        return this.props.colours[contestantNumber % this.props.colours.length]
    }

    numberStyle(cell, row, rowIndex, colIndex) {
        return {backgroundColor: this.getColour(row.contestantNumber)}
    }

    handleContestantLinkClick(contestantId) {
        this.props.setDisplay({displayType: CONTESTANT_DETAILS_DISPLAY, contestantId: contestantId})
        this.props.displayOnlyContestantTrack(contestantId)
        this.props.showLowerThirds(contestantId)
    }


    render() {
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.handleContestantLinkClick(row.contestantId)
            }
        }

        let scores = this.props.turningPointScores.sort((a, b) => {
            if (a.score > b.score) return 1;
            if (a.score < b.score) return -1;
            return 0
        }).map((c, index) => {
            return {
                ...c,
                rank: index + 1
            }
        })
        const columns = [
            {
                dataField: "colour",
                text: "  ",
                style: this.numberStyle

            },
            {
                dataField: "rank",
                text: "Rank"
            },
            {
                dataField: "contestantNumber",
                text: "#",
                hidden: true
            },
            {
                dataField: "contestantId",
                text: "",
                hidden: true
            },
            {
                dataField: "contestantName",
                text: "Contestant"
            },
            {
                dataField: "score",
                text: "Score"
            },
        ]


        return <BootstrapTable keyField={"rank"} data={scores} columns={columns} rowEvents={rowEvents}
                               classes={"table-dark"} wrapperClasses={"text-dark bg-dark"}
                               bootstrap4 striped hover condensed
        />


    }
}

const TurningPointDisplay = connect(mapStateToProps, {
    setDisplay,
    displayOnlyContestantTrack,
    showLowerThirds
})(ConnectedTurningPointDisplay)
export default TurningPointDisplay