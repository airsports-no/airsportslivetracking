import React, {Component} from "react";
import {connect} from "react-redux";
import {fetchContestList, fetchContestResults} from "../../actions/resultsService";
import {teamLongForm} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import "bootstrap/dist/css/bootstrap.min.css"
import {ProgressCircle} from "../contestantProgress";
import {AircraftBadge, ProfileBadge, TeamBadge} from "../teamBadges";
import {Link} from "react-router-dom";

const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.contestId],
    teams: state.teams
})

class ConnectedTaskSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
        if (!this.props.results) {
            this.props.fetchContestResults(this.props.contestId)
        }
    }


    buildData() {
        let data = {}
        this.props.contest.results.task_set.map((task) => {
            task.tasksummary_set.map((taskSummary) => {
                if (data[taskSummary.team] === undefined) {
                    data[taskSummary.team] = {}
                }
                Object.assign(data[taskSummary.team], {
                    [taskSummary.task.toFixed(0)]: taskSummary.points,
                })
            })
        })
        this.props.contest.results.contestsummary_set.map((summary) => {
            if (data[summary.team.id] === undefined) {
                data[summary.team.id] = {}
            }
            Object.assign(data[summary.team.id], {
                summary: summary.points,
                team: summary.team,
                key: summary.team.id + "_" + this.props.contestId
            })

        })
        return Object.values(data)
    }

    buildColumns() {
        return [{
            dataField: "team",
            text: "Team",
            formatter: (cell, row) => {
                return teamLongForm(cell)
            }

        }].concat(this.props.contest.results.task_set.map((task) => {
            return {
                dataField: task.id.toFixed(0),
                text: task.heading,
                sort: true
            }
        })).concat([{
            dataField: "summary",
            text: "Overall",
            sort: true
        }])
    }


    render() {
        if (!this.props.teams || !this.props.contest) return null
        return <div className={'row'}>
                <div className={"col-12"}>
                    <h1>{this.props.contest.results.name}</h1>
                    <BootstrapTable keyField={"key"} columns={this.buildColumns()} data={this.buildData()}/>
                </div>
            <Link to={"../../"}>Contest overview</Link>
        </div>
    }
}

const
    TaskSummaryResultsTable = connect(mapStateToProps, {
        fetchContestResults,
    })(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;