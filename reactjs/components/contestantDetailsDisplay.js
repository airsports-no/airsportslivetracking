import React, {Component} from "react";
import {connect} from "react-redux";
import {
    calculateProjectedScore,
    compareScoreAscending, compareScoreDescending,
    contestantShortForm,
    contestantTwoLines,
    ordinal_suffix_of
} from "../utilities";
import paginationFactory from "react-bootstrap-table2-paginator";
import BootstrapTable from "react-bootstrap-table-next";
import "bootstrap/dist/css/bootstrap.min.css"
import {Loading} from "./basicComponents";
import {ProgressCircle} from "./contestantProgress";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import {displayAllTracks, hideLowerThirds, setDisplay} from "../actions";
import {mdiMagnify, mdiPagePrevious, mdiPagePreviousOutline} from "@mdi/js";
import Icon from "@mdi/react";

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    logEntries: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].log_entries : null,
    initialLoading: state.initialLoadingContestantData[props.contestantId],
    progress: state.contestantData[props.contestantId].progress,
    contestant: state.contestants[props.contestantId],
    contestants: Object.keys(state.contestantData).map((key, index) => {
        return {
            track: state.contestantData[key].contestant_track,
            contestant: state.contestants[key]
        }
    }),
    navigationTask: state.navigationTask,
})

function FormatMessage(props) {
    const message = props.message
    let offset_string = null
    if (message.offset_string != null && message.offset_string.length > 0) {
        offset_string = " (" + message.offset_string + ")"
    }
    return <div className={"preWrap"}>{message.message} {offset_string}</div>
    // return <div className={"preWrap"}>{message.points.toFixed(2)} points {message.message} {offset_string}<span
    //     className={"gateTimesText"}>{message.times_string.length > 0 ? "\n" + message.times_string : null}</span></div>
}

class ConnectedContestantDetailsDisplay extends Component {
    constructor(props) {
        super(props)
        this.messagesEnd = null
    }

    calculateRank() {
        const contestants = this.props.contestants.filter((contestant) => {
            return contestant != null && contestant.contestant !== undefined
        })
        if (this.props.navigationTask.score_sorting_direction === "asc") {
            contestants.sort(compareScoreAscending)
        } else {
            contestants.sort(compareScoreDescending)
        }
        let rank = 1
        for (let contestant of contestants) {
            if (contestant.contestant.id === this.props.contestant.id) {
                return rank;
            }
            rank += 1
        }
        return -1
    }

    componentDidUpdate(prevProps) {
    }

    scrollToBottom() {
        this.messagesEnd.scrollIntoView({behavior: "smooth"});
    }

    resetToAllContestants() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }

    render() {
        const progress = Math.min(100, Math.max(0, this.props.progress.toFixed(1)))
        const finished = this.props.contestantData.current_state === "Finished"
        let projectedScore = calculateProjectedScore(this.props.contestantData.score, progress).toFixed(0)
        if (projectedScore === "99999") {
            projectedScore = "--"
        }
        const columns = [
            {
                text: "",
                headerFormatter: (column, colIndex, components) => {
                    return <div>
                        {ordinal_suffix_of(this.calculateRank())}<br/><Icon path={mdiPagePreviousOutline}
                                                                            title={"Logout"} size={1.1}
                                                                            color={"white"}/></div>

                },
                headerClasses: "text-center",
                dataField: "message.gate",
                formatter: (cell, row) => {
                    return <b>{cell}</b>
                },
                headerEvents: {
                    onClick: (e, column, columnIndex) => {
                        this.resetToAllContestants()
                    }
                }
            },

            {
                dataField: "message.points",
                text: "",
                headerFormatter: (column, colIndex, components) => {
                    return <div className={"contestant-details-header"}>
                        <div className={"row"}>
                            <div className={"col-6"}>{contestantTwoLines(this.props.contestant)}</div>
                            <div className={"col-2 text-center"}
                                 style={{color: "#e01b1c"}}>SCORE<br/>{this.props.contestantData.score.toFixed(this.props.scoreDecimals)}
                            </div>
                            <div className={"col-2 text-center"} style={{color: "orange"}}>EST<br/>{projectedScore}
                            </div>
                            <div className={"col-2 details-progress-circle"} style={{paddingTop: "5px"}}><ProgressCircle
                                progress={progress}
                                finished={finished}/>
                            </div>
                        </div>
                    </div>
                },
                headerAttrs: (column, colIndex) => ({
                    colSpan: 2
                }),
                formatter: (cell, row) => {
                    return cell.toFixed(2)
                },
                headerEvents: {
                    onClick: (e, column, columnIndex) => {
                        this.resetToAllContestants()
                    }
                }
            },

            {
                dataField: "message",
                text: "",
                formatter: (cell, row) => {
                    return <div className={"preWrap"}><FormatMessage message={cell}/></div>
                },
                headerEvents: {
                    onClick: (e, column, columnIndex) => {
                        this.resetToAllContestants()
                    }
                }
            }
        ]
        if (!this.props.contestantData) {
            return <div/>
        }
        let events = this.props.logEntries.map((line, index) => {
            return {
                key: this.props.contestantData.contestant_id + "details" + index,
                message: line,
            }
        })
        events.reverse()

        const paginationOptions = {
            sizePerPage: 20,
            hideSizePerPage: true,
            hidePageListOnlyOnePage: true
        };
        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.resetToAllContestants()
            }
        }

        const loading = this.props.initialLoading ? <Loading/> : <div/>
        return <div>
            {loading}
            <BootstrapTable keyField={"key"} data={events} columns={columns}
                            classes={"table-dark"} wrapperClasses={"text-dark bg-dark"}
                            bootstrap4 striped hover condensed rowEvents={rowEvents}
                            bordered={false}//pagination={paginationFactory(paginationOptions)}
            />
            <div style={{float: "left", clear: "both"}}
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
    hideLowerThirds
})(ConnectedContestantDetailsDisplay)
export default ContestantDetailsDisplay