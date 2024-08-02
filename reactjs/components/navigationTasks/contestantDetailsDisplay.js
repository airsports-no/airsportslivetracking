import React, { Component } from "react";
import { connect } from "react-redux";
import {
    calculateProjectedScore,
    compareScoreAscending, compareScoreDescending,
    contestantTwoLines,
    ordinal_suffix_of
} from "../../utilities";
import "bootstrap/dist/css/bootstrap.min.css"
import { Loading } from "../basicComponents";
import { ProgressCircle } from "./contestantProgress";
import { SIMPLE_RANK_DISPLAY } from "../../constants/display-types";
import { displayAllTracks, hideLowerThirds, removeHighlightContestantTable, setDisplay } from "../../actions";
import { mdiPagePreviousOutline } from "@mdi/js";
import Icon from "@mdi/react";
import { ResultsServiceTable } from "../resultsService/resultsServiceTable";

const mapStateToProps = (state, props) => ({
    logEntries: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].log_entries : null,
    initialLoading: state.initialLoadingContestantData[props.contestantId],
    progress: !state.initialLoadingContestantData[props.contestantId] && state.contestantProgress[props.contestantId] ? state.contestantProgress[props.contestantId] : 0,
    contestant: state.contestants[props.contestantId],
    currentState: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].current_state : null,
    calculatorFinished: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].calculator_finished : null,
    score: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track.score : null,
    navigationTask: state.navigationTask,
})

function FormatMessage(props) {
    const message = props.message
    let offset_string = null
    if (message.offset_string != null && message.offset_string.length > 0) {
        offset_string = " (" + message.offset_string + ")"
    }
    return <div className={"preWrap"}>{message.message} {offset_string}</div>
}

class ConnectedContestantDetailsDisplay extends Component {
    constructor(props) {
        super(props)
        this.messagesEnd = null
    }

    // calculateRank() {
    //     const contestants = this.props.contestants.filter((contestant) => {
    //         return contestant != null && contestant.contestant !== undefined
    //     })
    //     if (this.props.navigationTask.score_sorting_direction === "asc") {
    //         contestants.sort(compareScoreAscending)
    //     } else {
    //         contestants.sort(compareScoreDescending)
    //     }
    //     let rank = 1
    //     for (let contestant of contestants) {
    //         if (contestant.contestant.id === this.props.contestant.id) {
    //             return rank;
    //         }
    //         rank += 1
    //     }
    //     return -1
    // }

    componentDidUpdate(prevProps) {
    }

    resetToAllContestants() {
        this.props.setDisplay({ displayType: SIMPLE_RANK_DISPLAY })
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
        this.props.removeHighlightContestantTable(this.props.contestantId)
    }

    render() {
        const progress = Math.min(100, Math.max(0, this.props.progress.toFixed(1)))
        const finished = this.props.current_state === "Finished" || this.props.calculatorFinished
        let projectedScore = calculateProjectedScore(this.props.score, progress).toFixed(0)
        if (projectedScore === "99999") {
            projectedScore = "--"
        }
        const columns = [
            {
                id: "Rank",
                disableSortBy: true,
                Header: () => {
                    return <div className={"text-center"} style={{ width: "150px" }}>
                        {/* {ordinal_suffix_of(this.calculateRank())}<br/> */}
                        <Icon path={mdiPagePreviousOutline}
                            title={"Logout"} size={1.1}
                            color={"white"} />
                    </div>

                },
                accessor: (row, index) => {
                    return <b>{row.message.gate}</b>
                },
                onClick: (column) => {
                    this.resetToAllContestants()
                }
            },

            {
                id: "message.points",
                disableSortBy: true,
                Header: () => {
                    return <div className={"contestant-details-header"}>
                        <div className={"row"}>
                            <div className={"col-6"}>{contestantTwoLines(this.props.contestant)}</div>
                            <div className={"col-2 text-center"}
                                style={{ color: "#e01b1c" }}>SCORE<br />{this.props.score.toFixed(this.props.scoreDecimals)}
                            </div>
                            <div className={"col-2 text-center"} style={{ color: "orange" }}>EST<br />{projectedScore}
                            </div>
                            <div className={"col-2 details-progress-circle"} style={{ paddingTop: "5px" }}><ProgressCircle
                                progress={progress}
                                finished={finished} />
                            </div>
                        </div>
                    </div>
                },
                colSpan: 2,
                accessor: (row, index) => {
                    return <span style={{ width: "100px" }}>{row.message.points.toFixed(2)}</span>
                },
            },

            {
                id: "message",
                disableSortBy: true,
                Header: "",
                accessor: (row, index) => {
                    return <div className={"preWrap"}><FormatMessage message={row.message} /></div>
                },
                headerHidden: true
            }
        ]
        if (this.props.score === null) {
            return <div />
        }
        let events = this.props.logEntries.map((line, index) => {
            return {
                key: this.props.contestantId + "details" + index,
                message: line,
            }
        })
        events.reverse()

        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.resetToAllContestants()
            }
        }

        const loading = this.props.initialLoading ? <Loading /> : <div />
        return <div>
            {loading}
            <ResultsServiceTable data={events} columns={columns}
                className={"table table-striped table-hover table-sm table-dark"}
                rowEvents={rowEvents} headerRowEvents={rowEvents}
            />
            <div style={{ float: "left", clear: "both" }}
                ref={(el) => {
                    this.messagesEnd = el;
                }}>
            </div>
        </div>

    }
}

const ContestantDetailsDisplay = connect(mapStateToProps, {
    setDisplay,
    displayAllTracks,
    hideLowerThirds,
    removeHighlightContestantTable
})(ConnectedContestantDetailsDisplay)
export default ContestantDetailsDisplay