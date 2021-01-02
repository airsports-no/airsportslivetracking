import React, {Component} from "react";
import {connect} from "react-redux";
import {contestantShortForm} from "../utilities";
import paginationFactory from "react-bootstrap-table2-paginator";
import BootstrapTable from "react-bootstrap-table-next";
import "bootstrap/dist/css/bootstrap.min.css"
import {Loading} from "./basicComponents";
import {ProgressCircle} from "./contestantProgress";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import {displayAllTracks, hideLowerThirds, setDisplay} from "../actions";

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    initialLoading: state.initialLoadingContestantData[props.contestantId],
    contestant: state.contestants[props.contestantId]
})

function FormatMessage(props) {
    const message = props.message
    let string = message.points + " points for " + message.message;
    let offset_string = null
    if (message.offset_string != null) {
        offset_string = " (" + message.offset_string + ")"
    }
    let times = null
    if (message.planned != null && message.actual != null) {
        times = "\n(planned: " + message.planned + ", actual: " + message.actual + ")"
    }
    return <div className={"preWrap"}>{message.points} points {message.message} {offset_string}<span
        className={"gateTimesText"}>{times}</span></div>
}

class ConnectedContestantDetailsDisplay extends Component {
    resetToAllContestants() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }

    render() {
        const columns = [
            {
                text: "",
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
                dataField: "message",
                text: contestantShortForm(this.props.contestant) + " | " + this.props.contestantData.score + " points",
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
        const events = this.props.contestantData.score_log.map((line, index) => {
            return {
                key: this.props.contestantData.contestant_id + "details" + index,
                message: line,
            }
        })

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
        </div>

    }
}

const ContestantDetailsDisplay = connect(mapStateToProps, {
    setDisplay,
    displayAllTracks,
    hideLowerThirds
})(ConnectedContestantDetailsDisplay)
export default ContestantDetailsDisplay