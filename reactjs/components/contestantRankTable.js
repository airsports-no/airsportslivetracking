import React, {Component} from "react";
import {connect} from "react-redux";
import {compareScore, pz} from "../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import "bootstrap/dist/css/bootstrap.min.css"
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";
import {
    displayLatestStatus,
    displayOnlyContestantTrack,
    hideLatestStatus,
    setDisplay,
    toggleExpandedHeader
} from "../actions";

var moment = require("moment");
var momentDurationFormatSetup = require("moment-duration-format");

function getTrackingStateBackgroundClass(state) {
    if (["Tracking", "Procedure turn"].includes(state)) return "greenBackground";
    if (["Backtracking", "Failed procedure turn"].includes(state)) return "redBackground"
    return ""
}

const mapStateToProps = (state, props) => ({
    contestants: Object.keys(state.contestantData).map((key, index) => {
        return state.contestantData[key].contestant_track
    }),
    displayExpandedHeader: state.displayExpandedHeader
})


class ConnectedContestantRankTable extends Component {
    constructor(props) {
        super(props);
        this.rowStyle = this.rowStyle.bind(this)
        this.numberStyle = this.numberStyle.bind(this)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.handleStateHeaderClick = this.handleStateHeaderClick.bind(this)

    }

    handleStateHeaderClick() {
        this.props.toggleExpandedHeader()
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
            return contestant && contestant.current_state !== "Waiting..."
        })
        contestants.sort(compareScore)
        return contestants.map((contestant_track, index) => {
            return {
                colour: "",
                contestantNumber: contestant_track.contestant.contestant_number,
                contestantId: contestant_track.contestant.id,
                rank: index + 1,
                name: pz(contestant_track.contestant.contestant_number, 2) + ": " + contestant_track.contestant.team.pilot,
                score: contestant_track.score,
                currentState: contestant_track.current_state,
                lastGate: contestant_track.last_gate,
                lastGateTimeOffset: moment.duration(contestant_track.last_gate_time_offset, "seconds").format(),
                latestStatus: contestant_track.score_log.length > 0 ? contestant_track.score_log[contestant_track.score_log.length - 1] : ""
            }
        })
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
                dataField: "name",
                text: "Contestant"
            },
            {
                dataField: "score",
                text: "Score"
            },
            {
                dataField: "currentState",
                text: "State",
                classes: function callback(cell, row, rowIndex, colIndex) {
                    return getTrackingStateBackgroundClass(cell)
                },
                headerEvents: {
                    onClick: (e, column, columnIndex) => {
                        this.handleStateHeaderClick()
                    }
                }
            },
            {
                dataField: "latestStatus",
                text: "Latest status",
                hidden: !this.props.displayExpandedHeader
            },
            {
                dataField: "lastGate",
                text: "Last gate"
            },
            {
                dataField: "lastGateTimeOffset",
                text: "Time offset"
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
        return <BootstrapTable keyField={"rank"} data={this.buildData()} columns={columns}
                               bootstrap4 striped hover condensed pagination={paginationFactory(paginationOptions)}
                               rowEvents={rowEvents}/>
    }
}

const ContestantRankTable = connect(mapStateToProps, {
    setDisplay,
    displayOnlyContestantTrack,
    toggleExpandedHeader
})(ConnectedContestantRankTable)
export default ContestantRankTable