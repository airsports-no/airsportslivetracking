import React, {Component} from "react";
import {contestantShortForm} from "../utilities";
import {connect} from "react-redux";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";

const mapStateToProps = (state, props) => {
    let scores = [];
    if (state.contestantData !== undefined) {
        for (const contestantId in state.contestantData) {
            let value = state.contestantData[contestantId].contestant_track
            const contestant=state.contestants[contestantId]
            const initialLoading=state.initialLoadingContestantData[contestantId]
            if (value) {
                if (value.score_per_gate.hasOwnProperty(props.turningPointName)) {
                    scores.push({
                        colour: "",
                        score: initialLoading?"Loading...":value.score_per_gate[props.turningPointName],
                        contestantId: contestantId,
                        contestantName: contestantShortForm(contestant),
                        contestantNumber: contestant.contestant_number
                    })
                }
            }
        }
    }
    return {turningPointScores: scores}
}


class ConnectedTurningPointDisplay extends Component {
    constructor(props) {
        super(props);
        this.numberStyle = this.numberStyle.bind(this)
    }

    numberStyle(cell, row, rowIndex, colIndex) {
        return {backgroundColor: this.props.colourMap[row.contestantNumber]}
    }

    render() {
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
                dataField: "contestantName",
                text: "Contestant"
            },
            {
                dataField: "score",
                text: "Score"
            },
        ]


        const paginationOptions = {
            sizePerPage: 15,
            hideSizePerPage: true,
            hidePageListOnlyOnePage: true
        };
        return <BootstrapTable keyField={"rank"} data={scores} columns={columns}
                               classes={"table-dark table-responsive"} wrapperClasses={"text-dark bg-dark"}
                               bootstrap4 striped hover condensed //pagination={paginationFactory(paginationOptions)}
        />


    }
}

const TurningPointDisplay = connect(mapStateToProps)(ConnectedTurningPointDisplay)
export default TurningPointDisplay