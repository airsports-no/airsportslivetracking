import React, {Component} from "react";
import {connect} from "react-redux";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {
    fetchContestResults,
    resultsData,
    tasksData,
    teamsData, testsData
} from "../actions/resultsService";
import {teamRankingTable} from "../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import 'react-bootstrap-table2-toolkit/dist/react-bootstrap-table2-toolkit.min.css';
import "bootstrap/dist/css/bootstrap.min.css"
import {mdiChevronDown, mdiChevronUp, mdiGoKartTrack, mdiSort} from "@mdi/js";
import Icon from "@mdi/react";
import {Button} from "react-bootstrap";

const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.contestId],
    tasks: state.tasks[props.contestId],
    teams: state.teams,
    taskTests: state.taskTests[props.contestId],
})


function compareOverall(a, b) {
    if (a.points < b.points) {
        return -1;
    }
    if (a.points > b.points) {
        return 1;
    }
    // a must be equal to b
    return 0;
}


class ConnectedContestRankTable extends Component {
    constructor(props) {
        super(props)
        this.connectInterval = null;
        this.wsTimeOut = 1000
        this.state = {
            sortField: null,
            sortDirection: "asc"
        }
    }

    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    componentDidMount() {
        this.props.fetchContestResults(this.props.contestId)
        this.initiateSession()
    }

    initiateSession() {
        let getUrl = window.location;
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/contestresults/" + this.props.contestId + "/")
        this.client.onopen = () => {
            console.log("Client connected")
            clearTimeout(this.connectInterval)
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            if (data.type === "contest.teams") {
                this.props.teamsData(data.teams, this.props.contestId)
            }
            if (data.type === "contest.tasks") {
                this.props.tasksData(data.tasks, this.props.contestId)
            }
            if (data.type === "contest.tests") {
                this.props.testsData(data.tests, this.props.contestId)
            }
            if (data.type === "contest.results") {
                data.results.permission_change_contest = this.props.contest.results.permission_change_contest
                this.props.resultsData(data.results, this.props.contestId)
            }
        };
        this.client.onclose = (e) => {
            console.log(
                `Socket is closed. Reconnect will be attempted in ${Math.min(
                    10000 / 1000,
                    (this.timeout + this.timeout) / 1000
                )} second.`,
                e.reason
            );

            this.timeout = this.timeout + this.timeout; //increment retry interval
            this.connectInterval = setTimeout(() => this.check(), Math.min(10000, this.wsTimeOut)); //call check function after timeout
        };
        this.client.onerror = err => {
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );
            this.client.close();
        };
    }

    getOverallRank() {
        const direction = this.props.contest.results.summary_score_sorting_direction
        let sorted = this.props.contest.results.contestsummary_set.sort(compareOverall)
        if (direction === "desc") {
            sorted = sorted.reverse()
        }
        let ranks = {}
        let rank = 1
        sorted.map((overall) => {
            ranks[overall.team.id] = rank
            rank += 1
        })
        return ranks
    }

    getTaskToHighlight() {
        const tasks = this.props.tasks
        return tasks.find((task) => {
            return this.props.taskTests.find((taskTest) => {
                return taskTest.task === task.id && this.props.navigationTaskId === taskTest.navigation_task
            }) != null
        })
    }


    buildData() {
        let ranks = this.getOverallRank()

        let data = {}
        // Make sure that each team has a row even if it is and think
        this.props.contest.results.contest_teams.map((team) => {
            data[team] = {
                contestSummary: '-',
                team: this.props.teams[team],
                key: team + "_" + this.props.contestId,
                rank: ranks[team]
            }
            this.props.tasks.map((task) => {
                data[team]["task_" + task.id.toFixed(0)] = '-'
            })
        })
        this.props.contest.results.task_set.map((task) => {

            task.tasksummary_set.map((taskSummary) => {
                if (data[taskSummary.team] !== undefined) {
                    Object.assign(data[taskSummary.team], {
                        ["task_" + taskSummary.task.toFixed(0)]: taskSummary.points,
                    })
                }
            })
        })
        this.props.contest.results.contestsummary_set.map((summary) => {
            if (!summary.team || data[summary.team.id] === undefined) {
                return
            }
            Object.assign(data[summary.team.id], {
                contestSummary: summary.points,
            })

        })
        return Object.values(data)
    }

    buildColumns() {
        const taskToHighlight = this.getTaskToHighlight()
        const up = <Icon path={mdiChevronUp} title={"Ascending"} size={1}/>
        const down = <Icon path={mdiChevronDown} title={"Descending"} size={1}/>
        const contestSummaryColumn = {
            dataField: "contestSummary",
            text: "Σ",
            sort: true,
            editable: false,
            csvType: "number",
            onSort: (field, order) => {
                this.setState({
                    sortField: "contestSummary",
                    sortDirection: this.props.contest.results.summary_score_sorting_direction
                })
            },
            sortFunc: (a, b, order, dataField, rowA, rowB) => {
                if (b === '-') return -1
                if (a === '-') return 1
                if (order === 'asc') {
                    return a - b;
                }
                return b - a; // desc
            },
            sortCaret: (order, column) => {
                if (!order) return null;
                else if (order === 'asc') return up;
                else if (order === 'desc') return down;
                return null;
            },
            columnType: "contestSummary",
        }
        const teamColumn = [
            // {
            //     dataField: "colour",
            //     text: "  ",
            //     style: this.numberStyle
            //
            // },
            {
                dataField: "rank",
                text: " #",
                classes: "align-middle",
                sort: true,
                formatter: (cell, row) => {
                    return <span> {cell}</span>
                }

            },
            {
                dataField: "team",
                text: "CREW",
                formatter: (cell, row) => {
                    return <div className={"align-middle crew-name"}>{teamRankingTable(cell)}</div>
                }
            },
            contestSummaryColumn
        ]
        let columns = teamColumn
        const tasks = this.props.tasks.sort((a, b) => (a.index > b.index) ? 1 : ((b.index > a.index) ? -1 : 0))
        tasks.map((task) => {
            const dataField = "task_" + task.id.toFixed(0)
            columns.push({
                dataField: dataField,
                text: task.heading,
                sort: true,
                columnType: "task",
                editable: false,
                headerClasses: taskToHighlight && taskToHighlight.id === task.id ? "taskTitleName" : "",
                task: task.id,
                onSort: (field, order) => {
                    this.setState({
                        sortField: dataField,
                        sortDirection: task.summary_score_sorting_direction
                    })
                },
                sortFunc: (a, b, order, dataField, rowA, rowB) => {
                    if (b === '-') return -1
                    if (a === '-') return 1
                    if (order === 'asc') {
                        return a - b;
                    }
                    return b - a; // desc
                },
                sortCaret: (order, column) => {
                    if (!order) return null;
                    else if (order === 'asc') return up;
                    else if (order === 'desc') return down;
                    return null;
                },
                events: {},
            })
        })
        return columns
    }

    render() {
        if (!this.props.teams || !this.props.contest || !this.props.tasks || !this.props.taskTests) return null
        const c = this.buildColumns()
        const d = this.buildData()
        let sortDirection = this.state.sortField ? this.state.sortDirection : this.props.contest.results.summary_score_sorting_direction

        const defaultSorted = {
            dataField: this.state.sortField ? this.state.sortField : "contestSummary", // if dataField is not match to any column you defined, it will be ignored.
            order: sortDirection // desc or asc
        };
        return <BootstrapTable keyField="key" data={d} columns={c} sort={defaultSorted}
                               classes={"table-dark"} wrapperClasses={"text-dark bg-dark"}
                               bootstrap4 striped hover condensed
                               bordered={false}
        />
    }
}

const ContestRankTable = connect(mapStateToProps, {
    fetchContestResults,
    teamsData,
    tasksData,
    testsData,
    resultsData
})(ConnectedContestRankTable);
export default ContestRankTable;