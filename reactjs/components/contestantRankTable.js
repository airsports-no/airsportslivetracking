import React, {Component} from "react";
import {connect} from "react-redux";
import {compareScore, contestantShortForm, pz} from "../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import "bootstrap/dist/css/bootstrap.min.css"
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";
import {
    displayOnlyContestantTrack,
    setDisplay,
    toggleExpandedHeader
} from "../actions";
import {Loading} from "./basicComponents";
import {ProgressCircle, ProjectedScore} from "./contestantProgress";
import {CircularProgressbar, buildStyles} from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

var moment = require("moment");
var momentDurationFormatSetup = require("moment-duration-format");

function getTrackingStateBackgroundClass(state) {
    if (["Tracking", "Procedure turn"].includes(state)) return "greenBackground";
    if (["Backtracking", "Failed procedure turn"].includes(state)) return "redBackground"
    return ""
}

function calculateProjectedScore(score, progress) {
    if(progress<=0){
        return 99999
    }
    if (progress < 5) {
        return score
    }
    return (100 * score / progress)
}

const mapStateToProps = (state, props) => ({
    contestants: Object.keys(state.contestantData).map((key, index) => {
        return {
            track: state.contestantData[key].contestant_track,
            progress: state.contestantData[key].progress,
            initialLoading: state.initialLoadingContestantData[key],
            contestant: state.contestants[key]
        }
    }),
    displayExpandedHeader: state.displayExpandedHeader
})


class ConnectedContestantRankTable extends Component {
    constructor(props) {
        super(props);
        this.rowStyle = this.rowStyle.bind(this)
        this.numberStyle = this.numberStyle.bind(this)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.getStateFormat = this.getStateFormat.bind(this)
    }


    handleContestantLinkClick(contestantId) {
        this.props.setDisplay({displayType: CONTESTANT_DETAILS_DISPLAY, contestantId: contestantId})
        this.props.displayOnlyContestantTrack(contestantId)
    }


    numberStyle(cell, row, rowIndex, colIndex) {
        return {backgroundColor: this.props.colourMap[row.contestantNumber]}
    }

    rowStyle(row, rowIndex) {
        return {backgroundColor: this.props.colourMap[row.contestantNumber]}
    }


    buildData() {
        const contestants = this.props.contestants.filter((contestant) => {
            return contestant != null && contestant
        })
        contestants.sort(compareScore)
        return contestants.map((contestant, index) => {
            const progress = Math.min(100, Math.max(0, contestant.progress.toFixed(1)))
            return {
                key: contestant.contestant.id + "rack" + index,
                colour: "",
                contestantNumber: contestant.contestant.contestant_number,
                contestantId: contestant.contestant.id,
                rank: index + 1,
                progress: progress,
                name: contestantShortForm(contestant.contestant),
                score: contestant.track.score,
                projectedScore: calculateProjectedScore(contestant.track.score, progress),
                currentState: contestant.initialLoading ? "Loading..." : contestant.track.current_state,
                finished: contestant.track.current_state === "Finished",
                initialLoading: contestant.initialLoading,
                lastGate: contestant.track.last_gate,
                lastGateTimeOffset: moment.duration(contestant.track.last_gate_time_offset, "seconds").format([
                    moment.duration(1, "second"),
                    moment.duration(1, "minute"),
                    moment.duration(1, "hour")
                ], "d [days] hh:mm:ss"),
                latestStatus: contestant.track.score_log.length > 0 ? contestant.track.score_log[contestant.track.score_log.length - 1] : ""
            }
        })
    }

    getStateFormat(cell, row) {
        if (row.initialLoading) {
            return <Loading/>
        }
        return <div>{cell}</div>
    }


    getTrackProgressFormat(cell, row) {

    }

    render() {
        const columns = [
            {
                dataField: "colour",
                text: "  ",
                style: this.numberStyle

            },
            {
                dataField: "rank",
                text: "#",
                // headerEvents: {
                //     onClick: (e, column, columnIndex) => {
                //         this.handleExpandHeaderClick()
                //     }
                // },
                sort: true
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
                dataField: "name",
                text: "Team"
            },
            {
                dataField: "score",
                text: "Score"
            },
            {
                dataField: "progress",
                text: "Lap",
                formatter: (cell, row) => {
                    return <ProgressCircle progress={row.progress} finished={row.finished}/>
                }
            },
            {
                dataField: "projectedScore",
                text: "Est",
                style: (cell, row, rowIndex, colIndex) => {
                    return {color: "orange"}
                },
                formatter: (cell, row) => {
                    return cell.toFixed(0)
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
                dataField: "currentState",
                text: "State",
                hidden: !this.props.displayExpandedHeader,

                classes: function callback(cell, row, rowIndex, colIndex) {
                    return getTrackingStateBackgroundClass(cell)
                },
                // formatter: this.getStateFormat
            },
            {
                dataField: "latestStatus",
                text: "Latest status",
                hidden: true//!this.props.displayExpandedHeader
            },
            {
                dataField: "lastGate",
                text: "Gate",
                hidden: !this.props.displayExpandedHeader
            },
            {
                dataField: "lastGateTimeOffset",
                text: "Offset",
                hidden: !this.props.displayExpandedHeader
            }
        ]

        const rowEvents = {
            onClick: (e, row, rowIndex) => {
                this.handleContestantLinkClick(row.contestantId)
            }
        }

        const paginationOptions = {
            sizePerPage: 15,
            hideSizePerPage: true,
            hidePageListOnlyOnePage: true
        };
        return <BootstrapTable keyField={"key"} data={this.buildData()} columns={columns}
                               defaultSorted={[{dataField: "rank", order: "asc"}]}
                               classes={"table-dark"} wrapperClasses={"text-dark bg-dark"}
                               bootstrap4 striped hover condensed //pagination={paginationFactory(paginationOptions)}
                               rowEvents={rowEvents}/>
    }
}

const ContestantRankTable = connect(mapStateToProps, {
    setDisplay,
    displayOnlyContestantTrack,
    toggleExpandedHeader
})(ConnectedContestantRankTable)
export default ContestantRankTable