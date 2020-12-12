import React, {Component} from "react";
import {connect} from "react-redux";
import {contestantShortForm} from "../utilities";
import paginationFactory from "react-bootstrap-table2-paginator";
import BootstrapTable from "react-bootstrap-table-next";
import "bootstrap/dist/css/bootstrap.min.css"
import {Loading} from "./basicComponents";

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId] !== undefined ? state.contestantData[props.contestantId].contestant_track : null,
    initialLoading: state.initialLoadingContestantData[props.contestantId]
})

class ConnectedContestantDetailsDisplay extends Component {
    render() {
        const columns = [
            {
                dataField: "message",
                text: "Message",
            }
        ]
        if (!this.props.contestantData) {
            return <div/>
        }
        const events = this.props.contestantData.score_log.map((line, index) => {
            return {
                message: line
            }
        })
        const paginationOptions = {
            sizePerPage: 20,
            hideSizePerPage: true,
            hidePageListOnlyOnePage: true
        };
        const loading = this.props.initialLoading ? <Loading/> : <div/>
        return <div>
            {loading}
            <BootstrapTable keyField={"rank"} data={events} columns={columns}
                            bootstrap4 striped hover condensed pagination={paginationFactory(paginationOptions)}/>
        </div>

    }
}

const ContestantDetailsDisplay = connect(mapStateToProps)(ConnectedContestantDetailsDisplay)
export default ContestantDetailsDisplay