import React, {Component} from "react";
import {connect} from "react-redux";
import {
    calculateProjectedScore,
    teamRankingTable
} from "../../utilities";
import "bootstrap/dist/css/bootstrap.min.css"
import {SIMPLE_RANK_DISPLAY} from "../../constants/display-types";
import {
    displayAllTracks,
    displayOnlyContestantTrack, hideLowerThirds, highlightContestantTable,

    highlightContestantTrack, removeHighlightContestantTable,
    removeHighlightContestantTrack,
    setDisplay,
    showLowerThirds,
} from "../../actions";
import {Loading} from "../basicComponents";
import {ProgressCircle} from "./contestantProgress";
import 'react-circular-progressbar/dist/styles.css';
import {sortCaret} from "../resultsService/resultsTableUtilities";
import {ResultsServiceTable} from "../resultsService/resultsServiceTable";


const mapStateToProps = (state, props) => ({
    contestants: Object.keys(state.contestantData).map((key, index) => {
        return {
            track: state.contestantData[key].contestant_track,
            logEntries: state.contestantData[key].log_entries,
            progress: state.contestantData[key].progress,
            initialLoading: state.initialLoadingContestantData[key],
            contestant: state.contestants[key]
        }
    }),
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    highlight: state.highlightContestantTable,
    navigationTask: state.navigationTask,
})


class ConnectedContestantRankTable extends Component {
    constructor(props) {
        super(props);
        this.rowStyle = this.rowStyle.bind(this)
        this.numberStyle = this.numberStyle.bind(this)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.getStateFormat = this.getStateFormat.bind(this)
        this.selectedLine = null
        this.setHighlightedRef = element => {
            this.selectedLine = element;
        }
        this.columns = [
            {
                style:this.numberStyle,
                accessor: (row, index) => {
                    return ""
                },
                Header: () => {
                    return <span style={{width: 20 + 'px'}}></span>
                },
                id: "colour"
            },
            {
                Header: () => {
                    return <span style={{width: 50 + 'px'}}> #</span>
                },
                id: "Rank",
                disableSortBy: true,
                accessor: (row, rowIndex) => {
                    return <span>{rowIndex + 1}</span>
                }
            },
            {
                dataField: "pilotName",
                Header: "CREW",
                disableSortBy: true,
                accessor: (row, index) => {
                    return <div
                        className={"align-middle crew-name"}>{teamRankingTable(row.contestant.team, row.contestant.has_been_tracked_by_simulator)}</div>
                }
            },
            {
                dataField: "score",
                Header: "SCORE",
                sortDirection: this.props.navigationTask.score_sorting_direction,
                accessor: (row, index) => {
                    if (!row.hasStarted) {
                        return "--"
                    }
                    return <span className={"align-middle"}>{row.score.toFixed(this.props.scoreDecimals)}</span>
                }
            },
            {
                Header: "Σ",
                sortDirection: this.props.navigationTask.score_sorting_direction,
                hidden: !this.props.navigationTask.display_contestant_rank_summary,
                accessor: (row, index) => {
                    if (row.contest_summary != null) {
                        return <span
                            className={"align-middle"}>{row.contest_summary.toFixed(this.props.scoreDecimals)}</span>
                    } else {
                        return "--"
                    }
                },
            },
            {
                Header: "EST",
                sortDirection: this.props.navigationTask.score_sorting_direction,

                accessor: (row, index) => {
                    let value = row.projectedScore.toFixed(0)
                    if (value === "99999") {
                        value = "--"
                    }
                    if (this.props.highlight.includes(row.contestantId)) {
                        return <span ref={this.setHighlightedRef}>{value}</span>
                    }
                    return value
                },
            },
            {
                id: "progress",
                Header: () => {
                    return <span className={'text-center'}>LAP</span>
                },
                accessor: (row, index) => {
                    return <span className={'align-middle'} style={{width: 80 + 'px'}}><ProgressCircle
                        progress={row.progress} finished={row.finished}/></span>
                },
            },
        ]

        this.rowEvents = {
            onClick: (row) => {
                this.handleContestantLinkClick(row.contestantId)
            },
            onMouseEnter: (row) => {
                this.props.highlightContestantTrack(row.contestantId)
            },
            onMouseLeave: (row) => {
                this.props.removeHighlightContestantTrack(row.contestantId)
            }
        }

    }

    resetToAllContestants() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
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

    getColour(contestantNumber) {
        return this.props.colours[contestantNumber % this.props.colours.length]
    }


    numberStyle( row, rowIndex, colIndex) {
        return {backgroundColor: this.getColour(row.contestantNumber)}
    }

    rowStyle(row, rowIndex) {
        return {backgroundColor: this.getColour(row.contestantNumber)}
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
    }

    buildData() {
        const contestants = this.props.contestants.filter((contestant) => {
            return contestant != null && contestant.contestant !== undefined
        })
        // compareScore should be replaced depending on scorecard ascending or descending configuration
        // Initially simply reversed the list depending on ascending or descending in the scorecard
        // May be later support more complex scoring descriptions
        // if (this.props.navigationTask.score_sorting_direction === "asc") {
        //     contestants.sort(compareScoreAscending)
        // } else {
        //     contestants.sort(compareScoreDescending)
        // }
        return contestants.map((contestant, index) => {
            const progress = Math.min(100, Math.max(0, contestant.progress.toFixed(1)))
            return {
                key: contestant.contestant.id + "rack" + index,
                contestant: contestant.contestant,
                colour: "",
                contestantNumber: contestant.contestant.contestant_number,
                contestantId: contestant.contestant.id,
                rank: index + 1,
                dummy: null,
                progress: progress,
                hasStarted: contestant.track.current_state !== "Waiting...",
                name: teamRankingTable(contestant.contestant.team),
                pilotName: contestant.contestant.team.crew ? contestant.contestant.team.crew.member1.first_name : '',
                score: contestant.track.score,
                contest_summary: contestant.track.contest_summary,
                projectedScore: calculateProjectedScore(contestant.track.score, progress, contestant.track.contest_summary),
                finished: contestant.track.current_state === "Finished" || contestant.track.calculator_finished,
                initialLoading: contestant.initialLoading,
                className: this.props.highlight.includes(contestant.contestant.id)?"selectedContestantRow":""
            }
        })
    }

    getStateFormat(cell, row) {
        if (row.initialLoading) {
            return <Loading/>
        }
        return <div>{cell}</div>
    }

    debouncedBuildData() {
        return this.buildData()
    }

    render() {
        return <ResultsServiceTable data={this.debouncedBuildData()} columns={this.columns}
                                    className={"table table-dark table-striped table-hover table-condensed"}
                                    rowEvents={this.rowEvents}/>
    }
}

const
    ContestantRankTable = connect(mapStateToProps, {
        setDisplay,
        displayAllTracks,
        displayOnlyContestantTrack,
        showLowerThirds,
        hideLowerThirds,
        highlightContestantTrack,
        removeHighlightContestantTrack,
        highlightContestantTable,
        removeHighlightContestantTable
    })(ConnectedContestantRankTable)
export default ContestantRankTable