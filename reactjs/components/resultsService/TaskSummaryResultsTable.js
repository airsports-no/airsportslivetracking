import React, {Component} from "react";
import {connect} from "react-redux";
import {fetchContestList, fetchContestResults, hideTaskDetails, showTaskDetails} from "../../actions/resultsService";
import {teamLongForm, teamLongFormText} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import 'react-bootstrap-table2-toolkit/dist/react-bootstrap-table2-toolkit.min.css';
import "bootstrap/dist/css/bootstrap.min.css"
import {ProgressCircle} from "../contestantProgress";
import {AircraftBadge, ProfileBadge, TeamBadge} from "../teamBadges";
import {Link} from "react-router-dom";

import ToolkitProvider, {CSVExport} from 'react-bootstrap-table2-toolkit';

const {ExportCSVButton} = CSVExport;


const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.contestId],
    teams: state.teams,
    visibleTaskDetails: state.visibleTaskDetails
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
            task.tasktest_set.map((taskTest) => {
                taskTest.teamtestscore_set.map((testScore) => {
                    if (data[testScore.team] === undefined) {
                        data[testScore.team] = {}
                    }
                    Object.assign(data[testScore.team], {
                        [taskTest.id.toFixed(0)]: testScore.points
                    })
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

    anyDetailsVisible() {
        let visible = false
        Object.keys(this.props.visibleTaskDetails).map((task) => {
            if (this.props.visibleTaskDetails[task]) {
                visible = true
            }
        })
        return visible
    }

    buildColumns() {
        const teamColumn = {
            dataField: "team",
            text: "Team",
            formatter: (cell, row) => {
                return teamLongForm(cell)
            },
            csvFormatter: (cell, row) => {
                return teamLongFormText(cell)
            }

        }
        const contestSummaryColumn = {
            dataField: "summary",
            text: "Overall",
            sort: true,
            csvType: "number"
        }
        let columns = [teamColumn]
        this.props.contest.results.task_set.map((task) => {
            task.tasktest_set.map((taskTest) => {
                columns.push({
                    dataField: taskTest.id.toFixed(0),
                    text: taskTest.heading,
                    headerClasses: "text-muted",
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    csvType: "number"
                })
            });
            columns.push({
                dataField: task.id.toFixed(0),
                text: task.heading,
                sort: true,
                events: {
                    onClick: (e, column, columnIndex, row, rowIndex) => {
                        if (!this.props.visibleTaskDetails[task.id]) {
                            this.props.showTaskDetails(column.dataField)
                        } else {
                            this.props.hideTaskDetails(column.dataField)
                        }
                    }
                },
                hidden: !this.props.visibleTaskDetails[task.id] && this.anyDetailsVisible(),
                csvType: "number"
            })
        })
        columns.push(contestSummaryColumn)
        return columns
    }


    render() {
        if (!this.props.teams || !this.props.contest) return null
        const c = this.buildColumns()
        const d = this.buildData()
        const defaultSorted = [{
            dataField: 'summary', // if dataField is not match to any column you defined, it will be ignored.
            order: 'asc'// this.props.contest.results.summary_score_sorting_direction // desc or asc
        }];
        console.log(c)
        console.log(d)
        return <div className={'row'}>
            <div className={"col-12"}>
                <h1>{this.props.contest.results.name}</h1>
                <ToolkitProvider
                    keyField="key"
                    data={d}
                    columns={c}
                    exportCSV
                >
                    {
                        props => (
                            <div>
                                <BootstrapTable {...props.baseProps} defaultSorted={defaultSorted}
                                />
                                <hr/>
                                <ExportCSVButton {...props.csvProps}>Export CSV</ExportCSVButton>
                            </div>
                        )
                    }
                </ToolkitProvider>
            </div>
            <Link to={"../../"}>Contest overview</Link>
        </div>
    }
}

const
    TaskSummaryResultsTable = connect(mapStateToProps, {
        fetchContestResults,
        showTaskDetails,
        hideTaskDetails
    })(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;