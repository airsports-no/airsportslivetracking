import React, {Component} from "react";
import {connect} from "react-redux";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {
    createOrUpdateTask, createOrUpdateTaskTest, deleteTask, deleteTaskTest,
    fetchContestResults,
    fetchContestTeams, fetchTasks, fetchTaskTests, hideAllTaskDetails,
    hideTaskDetails, putContestSummary, putTaskSummary, putTestResult, resultsData,
    showTaskDetails, tasksData, teamsData, testsData
} from "../../actions/resultsService";
import {teamLongForm, teamLongFormText, teamRankingTable} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import 'react-bootstrap-table2-toolkit/dist/react-bootstrap-table2-toolkit.min.css';
import "bootstrap/dist/css/bootstrap.min.css"
import {Link} from "react-router-dom";

import ToolkitProvider, {CSVExport} from 'react-bootstrap-table2-toolkit';
import cellEditFactory from 'react-bootstrap-table2-editor';
import {Container, Modal, Button, Form} from "react-bootstrap";
import {
    mdiArrowCollapseHorizontal,
    mdiArrowExpandHorizontal, mdiChevronDown, mdiChevronLeft, mdiChevronRight, mdiChevronUp,
    mdiClose, mdiMagnifyMinus, mdiMagnifyPlus, mdiDeleteForever,
    mdiPencilOutline, mdiPlusBox, mdiSort
} from "@mdi/js";
import Icon from "@mdi/react";
import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    GET_TASK_TESTS_SUCCESSFUL,
    GET_TASKS_SUCCESSFUL
} from "../../constants/resultsServiceActionTypes";
import {sortCaret, sortFunc} from "../resultsTableUtilities";
import {Loading} from "../basicComponents";
import Navbar from "../navbar";

const {ExportCSVButton} = CSVExport;


const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.contestId],
    contestError: state.contestResultsErrors[props.contestId],
    tasks: state.tasks[props.contestId],
    taskTests: state.taskTests[props.contestId],
    teams: state.teams,
    visibleTaskDetails: state.visibleTaskDetails
})


class ConnectedTaskSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
        // if (!this.props.results) {
        // this.props.fetchContestResults(this.props.contestId)
        //     this.props.fetchContestTeams(this.props.contestId)
        //     this.props.fetchTasks(this.props.contestId)
        //     this.props.fetchTaskTests(this.props.contestId)
        // }
        this.state = {
            displayNewTaskModal: false,
            displayNewTaskTestModal: false,
            editTask: this.defaultTask(),
            editTaskTest: this.defaultTaskTest(),
            zoomedTask: null,
            sortField: null,
            sortDirection: "asc"
        }
        this.connectInterval = null;
        this.wsTimeOut = 1000
    }

    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    componentWillUnmount() {
        document.body.classList.remove("results-table-background")
        try {
            clearTimeout(this.timeout)
        } catch (e) {

        }
    }

    componentDidMount() {
        document.body.classList.add("results-table-background")
        this.periodicallyFetchResults()
        this.initiateSession()
    }

    periodicallyFetchResults() {
        this.props.fetchContestResults(this.props.contestId)
        this.timeout = setTimeout(() => this.periodicallyFetchResults(), 300000)
    }

    componentDidUpdate(prevProps) {
        if (this.props.match.params.task && !prevProps.tasks && this.props.tasks) {
            const task = this.props.tasks.find((task) => {
                return task.id === parseInt(this.props.match.params.task)
            })
            this.expandTask(task)
        }
    }

    deleteResultsTableLine(contestId, teamId) {
        let url = "/api/v1/contests/" + contestId + "/team_results_delete/"
        $.ajax({
            url: url,
            datatype: 'json',
            data: {team_id: teamId},
            method: "POST",
            cache: false,
            success: value => {
                this.props.fetchContestResults(contestId)
                // dispatch({type: DELETE_RESULTS_TABLE_TEAM_SUCCESSFUL, contestId: contestId, teamId: teamId})
            },
            error: error => alert(error)
        });
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
            if (this.props.contestError === undefined)
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


    defaultTask() {
        return {
            contest: this.props.contestId,
            summary_score_sorting_direction: "asc",
            name: "",
            heading: "",
            weight: 1.0,
            index: 0,
            autosum_scores: true
        }
    }

    defaultTaskTest(task) {
        return {
            contest: this.props.contest,
            sorting: "asc",
            name: "",
            heading: "",
            index: 0,
            weight: 1.0,
            task: task ? task : -1
        }
    }

    expandTask(task) {
        this.setState({zoomedTask: task})
        this.props.showTaskDetails(task.id)
    }

    collapseTask(task) {
        this.setState({zoomedTask: null})
        this.props.hideAllTaskDetails()
        if (this.props.match.params.task) {
            this.props.history.push("/resultsservice/" + this.props.contestId + "/taskresults/")
        }
    }

    createNewTask() {
        this.setState({displayNewTaskModal: false})
        this.props.createOrUpdateTask(this.props.contestId, this.state.editTask)
    }

    createNewTaskTest() {
        if (this.state.editTaskTest.task !== -1) {
            this.setState({displayNewTaskTestModal: false})
            this.props.createOrUpdateTaskTest(this.props.contestId, this.state.editTaskTest)
        }
    }


    newTaskModal() {
        return (
            <Modal show={this.state.displayNewTaskModal} onHide={() => this.setState({displayNewTaskModal: false})}
                   aria-labelledby="contained-modal-title-vcenter">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        {this.state.editMode === "new" ? <span>Add new task</span> : <span>Edit task</span>}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Container>
                        <Form.Group>
                            <Form.Label>Task name</Form.Label>
                            <Form.Control type={"text"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        name: e.target.value,
                                        heading: e.target.value
                                    }
                                })
                            }} value={this.state.editTask.name}/>
                            <Form.Label>Autosum test scores</Form.Label>
                            <Form.Check type={"checkbox"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        autosum_scores: e.target.checked,
                                    }
                                })
                            }} checked={this.state.editTask.autosum_scores}/>
                            <Form.Label>Task weight</Form.Label>
                            <Form.Control type={"number"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        weight: parseFloat(e.target.value),
                                    }
                                })
                            }}
                                          value={this.state.editTask.weight}
                                          step={0.1}
                            />
                            <Form.Label>Score sorting direction</Form.Label>
                            <Form.Control as={"select"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        summary_score_sorting_direction: e.target.value
                                    }
                                })
                            }} value={this.state.editTask.summary_score_sorting_direction}>
                                <option key={"asc"}
                                        value={"asc"}>Ascending
                                </option>
                                <option key={"desc"}
                                        value={"desc"}>Descending
                                </option>
                            </Form.Control>

                        </Form.Group>
                    </Container>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={() => this.createNewTask()}>Submit</Button>
                </Modal.Footer>
            </Modal>
        );
    }


    newTaskTestModal() {
        return (
            <Modal show={this.state.displayNewTaskTestModal}
                   onHide={() => this.setState({displayNewTaskTestModal: false})}
                   aria-labelledby="contained-modal-title-vcenter">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        {this.state.editMode === "new" ? <span>Add new test</span> : <span>Edit test</span>}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Container>
                        <Form.Group>
                            <Form.Label style={{display: "none"}}>Task</Form.Label>
                            <Form.Control style={{display: "none"}} as={"select"} onChange={(e) => {
                                this.setState({editTaskTest: {...this.state.editTaskTest, task: e.target.value}})
                            }} value={this.state.editTaskTest.task ? this.state.editTaskTest.task : -1}>
                                <option key={-1} value={-1}>--</option>
                                {this.props.tasks.map((task) => {
                                    return <option key={task.id}
                                                   value={task.id}>{task.name}</option>
                                })}
                            </Form.Control>
                            <Form.Label>Test name</Form.Label>
                            <Form.Control type={"text"} onChange={(e) => {
                                this.setState({
                                    editTaskTest: {
                                        ...this.state.editTaskTest,
                                        heading: e.target.value,
                                        name: e.target.value
                                    }
                                })
                            }}
                                          value={this.state.editTaskTest.name}
                            /><Form.Label>Test weight</Form.Label>
                            <Form.Control type={"number"} onChange={(e) => {
                                this.setState({
                                    editTaskTest: {
                                        ...this.state.editTaskTest,
                                        weight: parseFloat(e.target.value),
                                    }
                                })
                            }}
                                          value={this.state.editTaskTest.weight}
                                          step={0.1}
                            />
                            <Form.Label>Score sorting direction</Form.Label>
                            <Form.Control as={"select"} onChange={(e) => {
                                this.setState({editTaskTest: {...this.state.editTaskTest, sorting: e.target.value}})
                            }} value={this.state.editTaskTest.sorting}>
                                <option key={"asc"}
                                        value={"asc"}>Ascending
                                </option>
                                <option key={"desc"}
                                        value={"desc"}>Descending
                                </option>
                            </Form.Control>

                        </Form.Group>
                    </Container>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={() => this.createNewTaskTest()}>Submit</Button>
                </Modal.Footer>
            </Modal>
        );
    }

    moveTaskRight(e, taskId) {
        e.stopPropagation()
        const task = this.props.tasks.find((t) => {
            return t.id === taskId
        })
        const switchingWith = this.props.tasks.find((t) => {
            return t.index === task.index + 1
        })
        task.index += 1
        switchingWith.index -= 1
        this.props.createOrUpdateTask(this.props.contestId, task)
        this.props.createOrUpdateTask(this.props.contestId, switchingWith)
    }


    moveTaskLeft(e, taskId) {
        e.stopPropagation()
        const task = this.props.tasks.find((t) => {
            return t.id === taskId
        })
        const switchingWith = this.props.tasks.find((t) => {
            return t.index === task.index - 1
        })
        task.index -= 1
        switchingWith.index += 1
        this.props.createOrUpdateTask(this.props.contestId, task)
        this.props.createOrUpdateTask(this.props.contestId, switchingWith)
    }

    moveTestRight(e, testId) {
        e.stopPropagation()
        const test = this.props.taskTests.find((t) => {
            return t.id === testId
        })
        const switchingWith = this.props.taskTests.find((t) => {
            return t.index === test.index + 1 && t.task === test.task
        })
        test.index += 1
        switchingWith.index -= 1
        this.props.createOrUpdateTaskTest(this.props.contestId, test)
        this.props.createOrUpdateTaskTest(this.props.contestId, switchingWith)
    }


    moveTestLeft(e, testId) {
        e.stopPropagation()
        const test = this.props.taskTests.find((t) => {
            return t.id === testId
        })
        const switchingWith = this.props.taskTests.find((t) => {
            return t.index === test.index - 1 && t.task === test.task
        })
        test.index -= 1
        switchingWith.index += 1
        this.props.createOrUpdateTaskTest(this.props.contestId, test)
        this.props.createOrUpdateTaskTest(this.props.contestId, switchingWith)
    }


    buildData() {
        let data = {}
        // Make sure that each team has a row The gaps if it has any points, even if it is not registered
        this.props.contest.results.contestsummary_set.map((summary) => {
            let team = summary.team
            data[team.id] = {
                contestSummary: "-",
                team: team,
                key: team.id + "_" + this.props.contestId,
            }
            this.props.tasks.map((task) => {
                data[team.id]["task_" + task.id.toFixed(0)] = "-"
            })
            this.props.taskTests.map((taskTest) => {
                data[team.id]["test_" + taskTest.id.toFixed(0)] = "-"
            })
        })
        // Handle all the teams that have been registered, but maybe not competed
        this.props.contest.results.contest_teams.map((team) => {
            data[team] = {
                contestSummary: "-",
                team: this.props.teams[team],
                key: team + "_" + this.props.contestId,
            }
            this.props.tasks.map((task) => {
                data[team]["task_" + task.id.toFixed(0)] = "-"
            })
            this.props.taskTests.map((taskTest) => {
                data[team]["test_" + taskTest.id.toFixed(0)] = "-"
            })
        })
        this.props.contest.results.task_set.map((task) => {
            task.tasksummary_set.map((taskSummary) => {
                if (data[taskSummary.team] !== undefined) {
                    Object.assign(data[taskSummary.team], {
                        ["task_" + taskSummary.task.toFixed(0)]: taskSummary.points.toFixed(0),
                    })
                }
            })
            task.tasktest_set.map((taskTest) => {
                taskTest.teamtestscore_set.map((testScore) => {
                    if (data[testScore.team] === undefined) {
                        return
                    }
                    Object.assign(data[testScore.team], {
                        ["test_" + taskTest.id.toFixed(0)]: testScore.points.toFixed(0)
                    })
                })
            })
        })
        this.props.contest.results.contestsummary_set.map((summary) => {
            if (!summary.team || data[summary.team.id] === undefined) {
                return
            }
            Object.assign(data[summary.team.id], {
                contestSummary: summary.points.toFixed(0),
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
                let clearButton = null
                if (this.props.contest.results.permission_change_contest) {
                    clearButton = <a href={"#"} style={{float: "right"}}
                                     onClick={(e) => {
                                         e.stopPropagation()
                                         let confirmation = confirm("Are you sure you want to delete?")
                                         if (confirmation) {
                                             this.deleteResultsTableLine(this.props.contestId, cell.id)
                                         }
                                     }}><Icon
                        path={mdiDeleteForever} title={"Edit"} size={0.7}/></a>
                }
                return <div className={"align-middle crew-name"}>{clearButton}{teamRankingTable(cell)}</div>
            },
            csvFormatter: (cell, row) => {
                return teamLongFormText(cell)
            },
            editable: false,
        }

        const contestSummaryColumn = {
            dataField: "contestSummary",
            text: "Σ",
            sort: true,
            editable: !this.props.contest.results.autosum_scores,
            classes: "number-right " + (!this.props.contest.results.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : ""),
            csvType: "number",
            onSort: (field, order) => {
                this.setState({
                    sortField: "contestSummary",
                    sortDirection: this.props.contest.results.summary_score_sorting_direction
                })
            },
            sortFunc: sortFunc,
            sortCaret: sortCaret,
            columnType: "contestSummary",
            headerFormatter: (column, colIndex, components) => {
                return <span>
                    {components.sortElement} Σ
                </span>
            }
        }
        let columns = [teamColumn, contestSummaryColumn]

        const tasks = this.props.tasks.sort((a, b) => (a.index > b.index) ? 1 : ((b.index > a.index) ? -1 : 0))
        tasks.map((task, taskIndex) => {
            const taskTests = this.props.taskTests.filter((taskTest) => {
                return taskTest.task === task.id
            }).sort((a, b) => (a.index > b.index) ? 1 : ((b.index > a.index) ? -1 : 0))
            let hasNavTask = false
            taskTests.map((taskTest, taskTestIndex) => {
                const dataField = "test_" + taskTest.id.toFixed(0)
                hasNavTask |= taskTest.navigation_task !== null
                columns.push({
                    dataField: dataField,
                    text: taskTest.heading,
                    headerClasses: "text-muted",
                    headerStyle: {verticalAlign: 'top', height: "1px", minWidth: "80px"},
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    classes: "number-right " + (this.props.contest.results.permission_change_contest ? "editableCell" : ""),
                    csvType: "number",
                    onSort: (field, order) => {
                        this.setState({
                            sortField: dataField,
                            sortDirection: taskTest.sorting
                        })
                    },
                    sortFunc: sortFunc,
                    sortCaret: sortCaret,
                    columnType: "taskTest",
                    taskTest: taskTest.id,
                    headerFormatter: (column, colIndex, components) => {
                        let header = <span>{components.sortElement} {taskTest.heading}</span>
                        if (taskTest.navigation_task_link) {
                            header =
                                <a href={taskTest.navigation_task_link}>{components.sortElement} {taskTest.heading}</a>
                        }
                        let privileged = null
                        let move = null
                        if (this.props.contest.results.permission_change_contest) {
                            move = <div style={{position: "absolute", bottom: "0", right: "0"}}>
                                {taskTestIndex > 0 ?
                                    <a href={"#"} onClick={(e) => this.moveTestLeft(e, taskTest.id)}><Icon
                                        path={mdiChevronLeft} size={0.7}/></a> : null}
                                {taskTestIndex < taskTests.length - 1 ?
                                    <a href={"#"} onClick={(e) => this.moveTestRight(e, taskTest.id)}><Icon
                                        path={mdiChevronRight} size={0.7}/></a> : null}
                            </div>
                            privileged = <span style={{position: "absolute", bottom: "0", left: "0"}}>
                                <a href={"#"}
                                   onClick={(e) => {
                                       e.stopPropagation()

                                       this.setState({
                                           displayNewTaskTestModal: true,
                                           editTaskTest: taskTest,
                                           editMode: "edit"
                                       })
                                   }}><Icon
                                    path={mdiPencilOutline} title={"Edit"} size={0.7}/></a>
                                {!taskTest.navigation_task ?
                                    <a href={"#"}
                                       onClick={(e) => {
                                           e.stopPropagation()

                                           if (window.confirm("Are you sure you want to delete the task test?")) {
                                               this.props.deleteTaskTest(this.props.contestId, taskTest.id)
                                           }
                                       }}><Icon
                                        path={mdiClose} title={"Delete"} size={0.7}/></a> : null}
                                    </span>
                        }
                        return <div style={{position: "relative", height: "100%"}}>{header}{privileged}{move}</div>
                    }
                })
            });
            const dataField = "task_" + task.id.toFixed(0)
            columns.push({
                    dataField: dataField,
                    text: task.heading,
                    sort: true,
                    columnType: "task",
                    editable: !task.autosum_scores,
                    classes: "number-right " + (!task.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : ""),
                    headerStyle: {verticalAlign: 'top', height: "1px", minWidth: "80px"},
                    task: task.id,
                    onSort: (field, order) => {
                        this.setState({
                            sortField: dataField,
                            sortDirection: task.summary_score_sorting_direction
                        })
                    },
                    sortFunc: sortFunc,
                    sortCaret: sortCaret,
                    events: {},
                    hidden: !this.props.visibleTaskDetails[task.id] && this.anyDetailsVisible(),
                    csvType: "number",
                    // formatter: (cell, row) => {
                    //     <span>{cell}<Icon
                    //         path={mdiPencilOutline} title={"Edit"} size={0.7}
                    //         style={{verticalAlign: "top", textAlign: "right"}}/></span>
                    // },
                    headerFormatter: (column, colIndex, components) => {
                        // if (this.props.taskTests.filter((taskTest) => {
                        //     return taskTest.task === task.id
                        // }).length === 0 && this.props.visibleTaskDetails[task.id]) {
                        //     this.props.hideTaskDetails(task.id)
                        // }
                        let privilege_break = null
                        let privileged = null
                        let move = null
                        const common = <span>
                        {components.sortElement} {task.heading}
                    </span>
                        if (this.props.contest.results.permission_change_contest) {
                            privilege_break = <span><br/>&nbsp;</span>
                            if (!this.state.zoomedTask) {
                                move = <div style={{position: "absolute", bottom: "0", right: "0"}}>
                                    {taskIndex > 0 ?
                                        <a href={"#"} onClick={(e) => this.moveTaskLeft(e, task.id)}><Icon
                                            path={mdiChevronLeft} size={0.7}/></a> : null}
                                    {taskIndex < this.props.tasks.length - 1 ?
                                        <a href={"#"} onClick={(e) => this.moveTaskRight(e, task.id)}><Icon
                                            path={mdiChevronRight} size={0.7}/></a> : null}
                                </div>
                            }
                            privileged = <span style={{position: "absolute", bottom: "0", left: "0"}}>
                                <a href={"#"}
                                   onClick={(e) => {
                                       e.stopPropagation()

                                       this.setState({displayNewTaskModal: true, editTask: task, editMode: "edit"})
                                   }}><Icon
                                    path={mdiPencilOutline} title={"Edit"} size={0.7}/></a>
                                {!hasNavTask ?
                                    <a href={"#"}
                                       onClick={(e) => {
                                           e.stopPropagation()

                                           if (window.confirm("You sure you want to delete the task?")) {
                                               this.props.deleteTask(this.props.contestId, task.id)
                                           }
                                       }}><Icon
                                        path={mdiClose} title={"Delete"} size={0.7}/></a> : null}
                            </span>
                        }
                        return <div style={{position: "relative", height: "100%"}}>{this.props.visibleTaskDetails[task.id] ?
                            <a href={"#"}
                               onClick={(e) => {
                                   e.stopPropagation()
                                   this.collapseTask(task)
                               }}
                            >{common}</a> : <a href={"#"}
                                               onClick={(e) => {
                                                   e.stopPropagation()
                                                   this.expandTask(task)
                                               }}
                            >{common}</a>}{privilege_break}{privileged}
                            {/*{this.props.visibleTaskDetails[task.id] ? <a href={"#"}*/}
                            {/*                                             onClick={(e) => {*/}
                            {/*                                                 e.stopPropagation()*/}
                            {/*                                                 this.collapseTask(task)*/}
                            {/*                                             }}*/}
                            {/*    ><Icon path={mdiMagnifyMinus} size={0.7}/></a> :*/}
                            {/*    <a href={"#"}*/}
                            {/*       onClick={(e) => {*/}
                            {/*           e.stopPropagation()*/}
                            {/*           this.expandTask(task)*/}
                            {/*       }}*/}
                            {/*    ><Icon path={mdiMagnifyPlus} size={0.7}/></a>}*/}
                            {move}
                        </div>
                    }
                }
            )
        })
        return columns
    }

    render() {
        if (this.props.contestError) {
            return <div>
                <Navbar/>
                <div className={"container-xl"}>
                    <h4 className="alert alert-warning" role="alert">Failed loading
                        contest: {this.props.contestError.responseJSON.detail}</h4>
                    <p>Contact support or visit <a href={'https://home.airsports.no/faq/#contest-results-are-not-found'}>our FAQ</a> for more details.</p>
                </div>
            </div>
        }
        if (!this.props.teams || !this.props.contest || !this.props.tasks || !this.props.taskTests) return <Loading/>
        const c = this.buildColumns()
        const d = this.buildData()
        let sortDirection = this.state.sortField ? this.state.sortDirection : this.props.contest.results.summary_score_sorting_direction

        const defaultSorted = {
            dataField: this.state.sortField ? this.state.sortField : "contestSummary", // if dataField is not match to any column you defined, it will be ignored.
            order: sortDirection // desc or asc
        };
        const cellEdit = cellEditFactory({
            mode: 'click',
            blurToSave: true,
            afterSaveCell: (oldValue, newValue, row, column) => {
                const teamId = row.team.id
                if (newValue === undefined || newValue.length === 0) {
                    newValue = 0
                }
                if (column.columnType === "contestSummary") {
                    this.props.putContestSummary(this.props.contestId, teamId, newValue)
                } else if (column.columnType === "task") {
                    this.props.putTaskSummary(this.props.contestId, teamId, column.task, newValue)
                } else if (column.columnType === "taskTest") {
                    this.props.putTestResult(this.props.contestId, teamId, column.taskTest, newValue)
                }
                console.log(row)
            }
        });

        return <div>
            <Navbar/>
            <div className={"container-xl"}>
                <div className={"row results-table"}>
                    <div className={"col-12"}>

                        {
                            this.state.zoomedTask ?
                                <div><h3 className={"results-table-contest-name"}><Link className={"text-dark"}
                                                                                        to={"/resultsservice/"}>Results</Link> -> <a
                                    href={"#"} className={"text-dark"}
                                    onClick={() => this.collapseTask(this.state.zoomedTask)}>{this.props.contest.results.name}</a><br/>
                                    <b>{this.state.zoomedTask.name}</b>
                                    {this.props.contest.results.permission_change_contest ?
                                        <Button onClick={(e) => {
                                            this.setState({
                                                displayNewTaskTestModal: true,
                                                editTaskTest: this.defaultTaskTest(this.state.zoomedTask.id),
                                                editMode: "new"
                                            })
                                        }
                                        } style={{float: "right"}}>New test</Button> : null}</h3></div> :
                                <div><h3 className={"results-table-contest-name"}><Link className={"text-dark"}
                                                                                        to={"/resultsservice/"}>Results</Link><br/>
                                    <b>{this.props.contest.results.name}</b>
                                    {this.props.contest.results.permission_change_contest ?
                                        <Button style={{float: "right"}} onClick={(e) => {
                                            this.setState({
                                                displayNewTaskModal: true,
                                                editTask: this.defaultTask(),
                                                editMode: "new"
                                            })
                                        }}>New task</Button> : null}</h3></div>
                        }
                    </div>
                </div>
                <div className={"results-table"}>
                    <div className={""}>
                        <ToolkitProvider
                            keyField="key"
                            data={d}
                            columns={c}
                            exportCSV
                        >
                            {
                                props => (
                                    <div>
                                        <BootstrapTable {...props.baseProps} sort={defaultSorted}
                                                        classes={"table-dark bg-dark-transparent"}
                                                        wrapperClasses={"text-dark"}
                                                        bootstrap4 striped condensed
                                                        cellEdit={this.props.contest.results.permission_change_contest ? cellEdit : {}}
                                        />
                                        {this.props.contest.results.permission_change_contest ?
                                            <ExportCSVButton {...props.csvProps} className={"btn btn-secondary"}>Export
                                                CSV</ExportCSVButton> : null}
                                    </div>
                                )
                            }
                        </ToolkitProvider>
                    </div>
                    <div className={"alert alert-info alert-dismissable fade show"} style={{marginTop: "20px"}}>
                        <button type="button" className="close" data-dismiss="alert" aria-hidden="true">&#215;</button>
                        <h4 className="alert-heading">About the results table</h4>
                        Contest results consists of one or more tasks, and each task contains one or more tests. The
                        initial
                        view shows the summary score for each task in the contest. By clicking on the task name
                        you
                        can zoom into the individual test results within the task. Zoom out by clicking on the titles
                        above the table or the same task name in the rightmost column. For instance, a precision
                        navigation
                        task
                        will consist of three tests; a planning test, a navigation test, and an observation test. The
                        total
                        score of these three tests make up the score for the task.
                        {this.props.contest.results.permission_change_contest ? <p>
                            <hr/>
                            <a className={"alert-link"} href={"/static/documents/contest_results_admin.pdf"}>Administration
                                how-to guide</a>
                        </p> : null}

                    </div>
                    <div className={'text-dark'}>Photo by <a
                        href="https://unsplash.com/@tadeu?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Tadeu
                        Jnr</a> on <a
                        href="https://unsplash.com/s/photos/propeller-airplane?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText">Unsplash</a>
                    </div>
                </div>
                {this.newTaskModal()}
                {this.newTaskTestModal()}
            </div>
        </div>
    }
}

const
    TaskSummaryResultsTable = connect(mapStateToProps,
        {
            fetchContestResults,
            fetchContestTeams,
            showTaskDetails,
            hideTaskDetails,
            fetchTasks,
            fetchTaskTests,
            createOrUpdateTask,
            createOrUpdateTaskTest,
            deleteTask,
            deleteTaskTest,
            putContestSummary,
            putTaskSummary,
            putTestResult,
            teamsData,
            tasksData,
            testsData,
            resultsData,
            hideAllTaskDetails,
        }
    )(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;