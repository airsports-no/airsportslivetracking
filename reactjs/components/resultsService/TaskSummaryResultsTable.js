import React, {Component} from "react";
import {connect} from "react-redux";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {
    createOrUpdateTask, createOrUpdateTaskTest, deleteTask, deleteTaskTest,
    fetchContestResults,
    fetchContestTeams, fetchTasks, fetchTaskTests,
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
    mdiClose, mdiMagnifyMinus, mdiMagnifyPlus,
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

const {ExportCSVButton} = CSVExport;


const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.contestId],
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


    defaultTask() {
        return {
            contest: this.props.contestId,
            summary_score_sorting_direction: "asc",
            name: "",
            heading: "",
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
            task: task ? task : -1
        }
    }

    expandTask(task) {
        this.setState({zoomedTask: task})
        this.props.showTaskDetails(task.id)
    }

    collapseTask(task) {
        this.setState({zoomedTask: null})
        this.props.hideTaskDetails(task.id)
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
                            <Form.Label>Task</Form.Label>
                            <Form.Control as={"select"} onChange={(e) => {
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
        // Make sure that each team has a row even if it is and think
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
                        ["task_" + taskSummary.task.toFixed(0)]: taskSummary.points,
                    })
                }
            })
            task.tasktest_set.map((taskTest) => {
                taskTest.teamtestscore_set.map((testScore) => {
                    if (data[testScore.team] === undefined) {
                        return
                    }
                    Object.assign(data[testScore.team], {
                        ["test_" + taskTest.id.toFixed(0)]: testScore.points
                    })
                })
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
                return <div className={"align-middle crew-name"}>{teamRankingTable(cell)}</div>
            },
            csvFormatter: (cell, row) => {
                return teamLongFormText(cell)
            },
            editable: false

        }

        const contestSummaryColumn = {
            dataField: "contestSummary",
            text: "Σ",
            sort: true,
            editable: !this.props.contest.results.autosum_scores,
            classes: !this.props.contest.results.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : "",
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
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    classes: this.props.contest.results.permission_change_contest ? "editableCell" : "",
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
                        const header = <span>{components.sortElement} {taskTest.heading}</span>
                        let privileged = null
                        let move = null
                        if (this.props.contest.results.permission_change_contest) {
                            move = <div style={{verticalAlign: "baseline", textAlign: "right"}}>
                                {taskTestIndex > 0 ?
                                    <a href={"#"} onClick={(e) => this.moveTestLeft(e, taskTest.id)}><Icon
                                        path={mdiChevronLeft} size={0.7}/></a> : null}
                                {taskTestIndex < taskTests.length - 1 ?
                                    <a href={"#"} onClick={(e) => this.moveTestRight(e, taskTest.id)}><Icon
                                        path={mdiChevronRight} size={0.7}/></a> : null}
                            </div>
                            privileged = <span>
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
                        return <div>{header}{privileged}{move}</div>
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
                    classes: !task.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : "",
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
                        const common = <span>
                        {components.sortElement} {task.heading}
                    </span>
                        let privileged = null
                        let move = null
                        if (this.props.contest.results.permission_change_contest) {
                            if (!this.state.zoomedTask) {
                                move = <div style={{verticalAlign: "baseline", textAlign: "right"}}>
                                    {taskIndex > 0 ?
                                        <a href={"#"} onClick={(e) => this.moveTaskLeft(e, task.id)}><Icon
                                            path={mdiChevronLeft} size={0.7}/></a> : null}
                                    {taskIndex < this.props.tasks.length - 1 ?
                                        <a href={"#"} onClick={(e) => this.moveTaskRight(e, task.id)}><Icon
                                            path={mdiChevronRight} size={0.7}/></a> : null}
                                </div>
                            }
                            privileged = <span>
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
                        return <div>{common}{privileged}
                            {this.props.visibleTaskDetails[task.id] ? <a href={"#"}
                                                                         onClick={(e) => {
                                                                             e.stopPropagation()
                                                                             this.collapseTask(task)
                                                                         }}
                                ><Icon path={mdiMagnifyMinus} size={0.7}/></a> :
                                <a href={"#"}
                                   onClick={(e) => {
                                       e.stopPropagation()
                                       this.expandTask(task)
                                   }}
                                ><Icon path={mdiMagnifyPlus} size={0.7}/></a>}
                            {move}
                        </div>
                    }
                }
            )
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
        const cellEdit = cellEditFactory({
            mode: 'click',
            blurToSave: true,
            afterSaveCell: (oldValue, newValue, row, column) => {
                const teamId = row.team.id
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
            <div className={"row"}>
                <div className={"col-12"}>
                    {
                        this.state.zoomedTask ?
                            <div><h2><a href={"#"}
                                        onClick={() => this.collapseTask(this.state.zoomedTask)}>{this.props.contest.results.name}</a> ->
                                Tests
                                for {this.state.zoomedTask.name}
                                {this.props.contest.results.permission_change_contest ?
                                    <Button onClick={(e) => {
                                        this.setState({
                                            displayNewTaskTestModal: true,
                                            editTaskTest: this.defaultTaskTest(this.state.zoomedTask.id),
                                            editMode: "new"
                                        })
                                    }
                                    } style={{float: "right"}}>New test</Button> : null}</h2></div> :
                            <div><h2>{this.props.contest.results.name}
                                {this.props.contest.results.permission_change_contest ?
                                    <Button style={{float: "right"}} onClick={(e) => {
                                        this.setState({
                                            displayNewTaskModal: true,
                                            editTask: this.defaultTask(),
                                            editMode: "new"
                                        })
                                    }}>New task</Button> : null}</h2></div>
                    }
                </div>
            </div>
            <div className={"row"}>
                <div className={"col-12"}>
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
                                                    classes={"table-dark"}
                                                    wrapperClasses={"text-dark bg-dark"}
                                                    bootstrap4 striped condensed
                                                    cellEdit={this.props.contest.results.permission_change_contest ? cellEdit : {}}
                                    />
                                    <hr/>
                                    <ExportCSVButton {...props.csvProps}>Export CSV</ExportCSVButton>
                                </div>
                            )
                        }
                    </ToolkitProvider>
                </div>
            </div>
            {this.newTaskModal()}
            {this.newTaskTestModal()}
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
            resultsData
        }
    )(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;