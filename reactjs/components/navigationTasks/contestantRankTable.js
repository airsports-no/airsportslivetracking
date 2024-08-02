import React, { Component } from "react";
import { connect } from "react-redux";
import {
    calculateProjectedScore, compareScoreAscending, compareScoreDescending,
    teamRankingTable
} from "../../utilities";
import "bootstrap/dist/css/bootstrap.min.css"
import { SIMPLE_RANK_DISPLAY } from "../../constants/display-types";
import {
    displayAllTracks,
    displayOnlyContestantTrack, hideLowerThirds, highlightContestantTable,

    highlightContestantTrack, removeHighlightContestantTable,
    removeHighlightContestantTrack,
    setDisplay,
    showLowerThirds,
} from "../../actions";
import { Loading } from "../basicComponents";
import { ProgressCircle } from "./contestantProgress";
import 'react-circular-progressbar/dist/styles.css';
import { ResultsServiceTable } from "../resultsService/resultsServiceTable";


const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData,
    contestantProgress: state.contestantProgress,
    initialLoading: state.initialLoadingContestantData,
    contestants: state.contestants,
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
                style: this.numberStyle,
                accessor: (row, index) => {
                    return ""
                },
                Header: () => {
                    return <span style={{ width: 20 + 'px' }}></span>
                },
                id: "colour",
                disableSortBy: true,
            },
            {
                Header: () => {
                    return <span style={{ width: 50 + 'px' }}> #</span>
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
                        className={"align-middle crew-name"}>{row.contestant?teamRankingTable(row.contestant.team, row.contestant.has_been_tracked_by_simulator):''}</div>
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
                },
                sortType: compareScoreAscending
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
                sortType: (rowA, rowB, id, desc) => {
                    if (rowA.original.contest_summary > rowB.original.contest_summary) return 1;
                    if (rowB.original.contest_summary > rowA.original.contest_summary) return -1;
                    return 0;
                }

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
                sortType: (rowA, rowB, id, desc) => {
                    if (rowA.original.projectedScore > rowB.original.projectedScore) return 1;
                    if (rowB.original.projectedScore > rowA.original.projectedScore) return -1;
                    return 0;
                }
            },
            {
                id: "progress",
                Header: () => {
                    return <span className={'text-center'}>LAP</span>
                },
                accessor: (row, index) => {
                    return <span className={'align-middle'} style={{ width: 80 + 'px' }}><ProgressCircle
                        progress={row.progress} finished={row.finished} /></span>
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
        this.props.setDisplay({ displayType: SIMPLE_RANK_DISPLAY })
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


    numberStyle(row, rowIndex, colIndex) {
        return { backgroundColor: this.getColour(row.contestantNumber) }
    }

    rowStyle(row, rowIndex) {
        return { backgroundColor: this.getColour(row.contestantNumber) }
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
    }

    buildData() {
        const contestantData = Object.values(this.props.contestantData)//.filter((cd)=>this.props.contestants[cd.contestant_id]!== undefined)
        // compareScore should be replaced depending on scorecard ascending or descending configuration
        // Initially simply reversed the list depending on ascending or descending in the scorecard
        // May be later support more complex scoring descriptions
        if (this.props.navigationTask.score_sorting_direction === "asc") {
            contestantData.sort(compareScoreAscending)
        } else {
            contestantData.sort(compareScoreDescending)
        }
        return contestantData.map((contestantData, index) => {
            const contestant = this.props.contestants[contestantData.contestant_id]
            const progress=this.props.contestantProgress[contestantData.contestant_id]!==undefined?Math.min(100, Math.max(0, this.props.contestantProgress[contestantData.contestant_id].toFixed(1))):0
            return {
                key: contestantData.contestant_id + "track" + index,
                track: contestantData.contestant_track,
                contestant: contestant !== undefined ?contestant:null,
                colour: "",
                contestantNumber: contestant !== undefined ?contestant.contestant_number:null,
                contestantId: contestantData.contestant_id,
                rank: index + 1,
                dummy: null,
                progress: progress,
                hasStarted: contestantData.contestant_track !== undefined && contestantData.contestant_track.current_state !== "Waiting...",
                name: contestant !== undefined ?teamRankingTable(contestant.team):'',
                pilotName: contestant !== undefined ?contestant.team.crew ? contestant.team.crew.member1.first_name : '':'',
                score: contestantData.contestant_track !== undefined ? contestantData.contestant_track.score : 0,
                contest_summary: contestantData.contestant_track !== undefined ? contestantData.contestant_track.contest_summary : 0,
                projectedScore: contestantData.contestant_track !== undefined ? calculateProjectedScore(contestantData.contestant_track.score, progress, contestantData.contestant_track.contest_summary) : 9999,
                finished: contestantData.contestant_track !== undefined ? contestantData.contestant_track.current_state === "Finished" || contestantData.contestant_track.calculator_finished : false,
                initialLoading: this.props.initialLoading[contestantData.contestant_id],
                className: this.props.highlight.includes(contestantData.contestant_id) ? "selectedContestantRow" : ""
            }
        })

    }

    getStateFormat(cell, row) {
        if (row.initialLoading) {
            return <Loading />
        }
        return <div>{cell}</div>
    }

    debouncedBuildData() {
        return this.buildData()
    }

    render() {
        return <ResultsServiceTable data={this.debouncedBuildData()} columns={this.columns}
            className={"table table-dark table-striped table-hover table-sm"}
            rowEvents={this.rowEvents} initialState={{
                sortBy: [
                    {
                        id: "SCORE",
                        desc: this.props.navigationTask.score_sorting_direction === "desc"
                    }
                ]
            }}
        />
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