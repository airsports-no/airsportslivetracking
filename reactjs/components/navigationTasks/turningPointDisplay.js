import React, {Component} from "react";
import {contestantShortForm} from "../../utilities";
import {connect} from "react-redux";
import {
    displayAllTracks,
    displayOnlyContestantTrack, hideLowerThirds,
    highlightContestantTable,
    removeHighlightContestantTrack,
    removeHighlightContestantTable,
    setDisplay,
    showLowerThirds
} from "../../actions";
import {ResultsServiceTable} from "../resultsService/resultsServiceTable";

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
    return {
        turningPointScores: scores, highlight: state.highlightContestantTable,
    }
}


class ConnectedTurningPointDisplay extends Component {
    constructor(props) {
        super(props);
        this.numberStyle = this.numberStyle.bind(this)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.columns = [
            {
                accessor: (row, index) => {
                    return ""
                },
                Header: () => {
                    return <span style={{width: 20 + 'px'}}></span>
                },
                id: "colour",
                disableSortBy: true,
                style: this.numberStyle
            },
            {
                accessor: "rank",
                disableSortBy: true,
                Header: "Rank"
            },
            {
                accessor: "contestantName",
                disableSortBy: true,
                Header: "Contestant"
            },
            {
                accessor: "score",
                disableSortBy: true,
                Header: "Score"
            },
        ]
    }


    getColour(contestantNumber) {
        return this.props.colours[contestantNumber % this.props.colours.length]
    }

    numberStyle(row, rowIndex, colIndex) {
        return {backgroundColor: this.getColour(row.contestantNumber)}
    }

    resetToAllContestants() {
        // this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
        for (let id of this.props.highlight) {
            this.props.removeHighlightContestantTable(id)
        }
    }

    handleContestantLinkClick(contestantId) {
        this.resetToAllContestants()
        if (!this.props.highlight.includes(contestantId)) {
            this.props.displayOnlyContestantTrack(contestantId)
            this.props.showLowerThirds(contestantId)
            this.props.removeHighlightContestantTrack(contestantId)
            this.props.highlightContestantTable(contestantId)
        }
    }


    render() {
        const rowEvents = {
            onClick: (row) => {
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


        return <ResultsServiceTable data={scores} columns={this.columns} rowEvents={rowEvents}
                                    className={"table table-striped table-hover table-sm table-dark"}
        />


    }
}

const TurningPointDisplay = connect(mapStateToProps, {
    setDisplay,
    displayOnlyContestantTrack,
    showLowerThirds,
    removeHighlightContestantTrack,
    highlightContestantTable,
    displayAllTracks,
    hideLowerThirds,
    removeHighlightContestantTable
})(ConnectedTurningPointDisplay)
export default TurningPointDisplay