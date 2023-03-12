import React, {Component} from "react";
import {connect} from "react-redux";
import {
    calculateProjectedScore,
    compareScoreAscending, compareScoreDescending,
    teamRankingTable
} from "../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import "bootstrap/dist/css/bootstrap.min.css"
import 'react-bootstrap-table-next/dist/react-bootstrap-table2.min.css';
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import {
    displayAllTracks,
    displayOnlyContestantTrack, hideLowerThirds, highlightContestantTable,

    highlightContestantTrack, removeHighlightContestantTable,
    removeHighlightContestantTrack,
    setDisplay,
    showLowerThirds,
} from "../actions";
import {Loading} from "./basicComponents";
import {ProgressCircle} from "./contestantProgress";
import 'react-circular-progressbar/dist/styles.css';
import {sortCaret} from "./resultsTableUtilities";


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
                dataField: "colour",
                text: "",
                style: this.numberStyle,
                headerStyle: {width: '20px'}
            },
            {
                dataField: "rank",
                text: " #",
                classes: "align-middle",
                headerStyle: {width: '50px'},
                sort: false,
                formatter: (cell, row, rowIndex) => {
                    return <span>{rowIndex + 1}</span>
                }
            },
            {
                dataField: "contestantNumber",
                text: "#",
                hidden: true,
            },
            {
                dataField: "contestantId",
                text: "",
                hidden: true
            },
            {
                dataField: "pilotName",
                text: "CREW",
                sort: false,
                classes: "align-middle crew-name",
                formatter: (cell, row) => {
                    return <div
                        className={"align-middle crew-name"}>{teamRankingTable(row.contestant.team, row.contestant.has_been_tracked_by_simulator)}</div>
                }
            },
            {
                dataField: "score",
                text: "SCORE",
                classes: "align-middle",
                sort: true,
                sortCaret: sortCaret,
                headerFormatter: (column, colIndex, components) => {
                    return <span>
                    SCORE{components.sortElement}
                </span>
                },
                formatter: (cell, row) => {
                    if (!row.hasStarted) {
                        return "--"
                    }
                    return cell.toFixed(this.props.scoreDecimals)
                }
            },
            {
                dataField: "contest_summary",
                text: "Σ",
                classes: "align-middle",
                sort: true,
                hidden: !this.props.navigationTask.display_contestant_rank_summary,
                sortCaret: sortCaret,
                headerFormatter: (column, colIndex, components) => {
                    return <span>
                    Σ{components.sortElement}
                </span>
                },
                formatter: (cell, row) => {
                    if (cell != null) {
                        return cell.toFixed(this.props.scoreDecimals)
                    } else {
                        return "--"
                    }
                },
            },
            {
                dataField: "projectedScore",
                text: "EST",
                classes: "align-middle",
                style: (cell, row, rowIndex, colIndex) => {
                    return {color: "orange"}
                },
                sortCaret: sortCaret,
                headerFormatter: (column, colIndex, components) => {
                    return <span>
                    EST{components.sortElement}
                </span>
                },

                formatter: (cell, row) => {
                    let value = cell.toFixed(0)
                    if (value === "99999") {
                        value = "--"
                    }
                    if (this.props.highlight.includes(row.contestantId)) {
                        return <span ref={this.setHighlightedRef}>{value}</span>
                    }
                    return value
                },
                sort: true,
                sortFunc: (a, b, order, dataField, rowA, rowB) => {
                    if (order === 'asc') {
                        return b - a;
                    }
                    return a - b; // desc
                }
            },
            {
                dataField: "progress",
                text: "LAP",
                formatter: (cell, row) => {
                    return <ProgressCircle progress={row.progress} finished={row.finished}/>
                },
                headerClasses: "text-center",
                style: (cell, row, rowIndex, colIndex) => {
                    return {width: 80 + 'px'}
                },
                classes: "align-middle"
            },
        ]

        this.rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.handleContestantLinkClick(row.contestantId)
            },
            onMouseEnter: (e, row, rowIndex) => {
                this.props.highlightContestantTrack(row.contestantId)
            },
            onMouseLeave: (e, row, rowIndex) => {
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


    numberStyle(cell, row, rowIndex, colIndex) {
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
        if (this.props.navigationTask.score_sorting_direction === "asc") {
            contestants.sort(compareScoreAscending)
        } else {
            contestants.sort(compareScoreDescending)
        }
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
        const rowClasses = (row, rowIndex) => {
            if (this.props.highlight.includes(row.contestantId)) {
                return "selectedContestantRow"
            }
        }

        return <BootstrapTable keyField={"key"} data={this.debouncedBuildData()} columns={this.columns}
                               rowClasses={rowClasses}
                               defaultSorted={[{dataField: "rank", order: "asc"}]}
                               classes={"table-dark"} wrapperClasses={"text-dark bg-dark"}
                               bootstrap4 striped hover condensed
                               bordered={false}
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