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
import {teamLongForm, teamLongFormText} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import 'react-bootstrap-table2-toolkit/dist/react-bootstrap-table2-toolkit.min.css';
import "bootstrap/dist/css/bootstrap.min.css"
import {Link} from "react-router-dom";

import ToolkitProvider, {CSVExport} from 'react-bootstrap-table2-toolkit';
import cellEditFactory from 'react-bootstrap-table2-editor';
import {Container, Modal, Button, Form} from "react-bootstrap";
import {
    mdiArrowCollapseHorizontal,
    mdiArrowExpandHorizontal,
    mdiClose,
    mdiPencilOutline, mdiSort
} from "@mdi/js";
import Icon from "@mdi/react";
import {
    GET_CONTEST_RESULTS_SUCCESSFUL,
    GET_CONTEST_TEAMS_LIST_SUCCESSFUL,
    GET_TASK_TESTS_SUCCESSFUL,
    GET_TASKS_SUCCESSFUL
} from "../../constants/resultsServiceActionTypes";

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
                        Add new task
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
                            <Form.Label>Task index</Form.Label>
                            <Form.Control type={"number"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        index: e.target.value,
                                    }
                                })
                            }} value={this.state.editTask.index}/>
                            <Form.Label>Autosum test scores</Form.Label>
                            <Form.Check type={"checkbox"} onChange={(e) => {
                                this.setState({
                                    editTask: {
                                        ...this.state.editTask,
                                        autosum_scores: e.target.checked,
                                    }
                                })
                            }} checked={this.state.editTask.autosum_scores}/>
                            <Form.Label>Sorting direction</Form.Label>
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
                        Add new task
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
                            <Form.Label>Task test index</Form.Label>
                            <Form.Control type={"number"} onChange={(e) => {
                                this.setState({
                                    editTaskTest: {
                                        ...this.state.editTaskTest,
                                        index: e.target.value,
                                    }
                                })
                            }} value={this.state.editTaskTest.index}/>
                            <Form.Label>Sorting direction</Form.Label>
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


    buildData() {
        let data = {}
        // Make sure that each team has a row even if it is and think
        this.props.contest.results.contest_teams.map((team) => {
            data[team] = {
                contestSummary: 0,
                team: this.props.teams[team],
                key: team + "_" + this.props.contestId,
            }
            this.props.tasks.map((task) => {
                data[team]["task_" + task.id.toFixed(0)] = 0
            })
            this.props.taskTests.map((taskTest) => {
                data[team]["test_" + taskTest.id.toFixed(0)] = 0
            })
        })
        this.props.contest.results.task_set.map((task) => {
            task.tasksummary_set.map((taskSummary) => {
                // if (data[taskSummary.team] === undefined) {
                //     data[taskSummary.team] = {}
                // }
                Object.assign(data[taskSummary.team], {
                    ["task_" + taskSummary.task.toFixed(0)]: taskSummary.points,
                })
            })
            task.tasktest_set.map((taskTest) => {
                taskTest.teamtestscore_set.map((testScore) => {
                    if (data[testScore.team] === undefined) {
                        data[testScore.team] = {}
                    }
                    Object.assign(data[testScore.team], {
                        ["test_" + taskTest.id.toFixed(0)]: testScore.points
                    })
                })
            })
        })
        this.props.contest.results.contestsummary_set.map((summary) => {
            if (data[summary.team.id] === undefined) {
                data[summary.team.id] = {}
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
                return teamLongForm(cell)
            },
            csvFormatter: (cell, row) => {
                return teamLongFormText(cell)
            },
            editable: false

        }
        const contestSummaryColumn = {
            dataField: "contestSummary",
            text: "Overall",
            sort: true,
            editable: !this.props.contest.results.autosum_scores,
            csvType: "number",
            sortCaret: (order, column) => {
                if (!order) return (<span>&nbsp;&nbsp;Desc/Asc</span>);
                else if (order === 'asc') return (<span>&nbsp;&nbsp;Desc/<font color="red">Asc</font></span>);
                else if (order === 'desc') return (<span>&nbsp;&nbsp;<font color="red">Desc</font>/Asc</span>);
                return null;
            },
            columnType: "contestSummary",
            headerFormatter: (column, colIndex, components) => {
                return <div>
                    Overall&nbsp;&nbsp;
                    <Button variant={"secondary"}
                            onClick={(e) => {
                                this.setState({
                                    sortField: "contestSummary",
                                    sortDirection: this.props.contest.results.summary_score_sorting_direction
                                })
                            }}><Icon
                        path={mdiSort} title={"Sort"} size={0.8}/></Button>
                    {components.sortElement}
                </div>
            }
        }
        let columns = [teamColumn]
        const tasks = this.props.tasks.sort((a, b) => (a.index > b.index) ? 1 : ((b.index > a.index) ? -1 : 0))
        tasks.map((task) => {
            const taskTests = this.props.taskTests.filter((taskTest) => {
                return taskTest.task === task.id
            }).sort((a, b) => (a.index > b.index) ? 1 : ((b.index > a.index) ? -1 : 0))
            taskTests.map((taskTest) => {
                const dataField = "test_" + taskTest.id.toFixed(0)
                columns.push({
                    dataField: dataField,
                    text: taskTest.heading,
                    headerClasses: "text-muted",
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    csvType: "number",
                    sortCaret: (order, column) => {
                        if (!order) return (<span>&nbsp;&nbsp;Desc/Asc</span>);
                        else if (order === 'asc') return (<span>&nbsp;&nbsp;Desc/<font color="red">Asc</font></span>);
                        else if (order === 'desc') return (<span>&nbsp;&nbsp;<font color="red">Desc</font>/Asc</span>);
                        return null;
                    },
                    columnType: "taskTest",
                    taskTest: taskTest.id,
                    headerFormatter: (column, colIndex, components) => {
                        const common = <div>{task.heading}-><br/>{taskTest.heading}&nbsp;&nbsp;
                            <Button variant={"secondary"}
                                    onClick={(e) => {
                                        this.setState({
                                            sortField: dataField,
                                            sortDirection: taskTest.sorting
                                        })
                                    }}><Icon
                                path={mdiSort} title={"Sort"} size={0.8}/></Button>
                            {components.sortElement}
                        </div>
                        if (this.props.contest.results.permission_change_contest) {
                            return <div>
                                {common}
                                <Button variant={"danger"}
                                        onClick={(e) => {
                                            if (window.confirm("Are you sure you want to delete the task test?")) {
                                                this.props.deleteTaskTest(this.props.contestId, taskTest.id)
                                            }
                                        }}><Icon
                                    path={mdiClose} title={"Delete"} size={0.8}/></Button>
                                <Button variant={"secondary"}
                                        onClick={(e) => {
                                            this.setState({displayNewTaskTestModal: true, editTaskTest: taskTest})
                                        }}><Icon
                                    path={mdiPencilOutline} title={"Edit"} size={0.8}/></Button>

                            </div>
                        }
                        return common
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
                task: task.id,
                sortCaret: (order, column) => {
                    if (!order) return (<span>&nbsp;&nbsp;Desc/Asc</span>);
                    else if (order === 'asc') return (<span>&nbsp;&nbsp;Desc/<font color="red">Asc</font></span>);
                    else if (order === 'desc') return (<span>&nbsp;&nbsp;<font color="red">Desc</font>/Asc</span>);
                    return null;
                },
                events: {},
                hidden: !this.props.visibleTaskDetails[task.id] && this.anyDetailsVisible(),
                csvType: "number",
                headerFormatter: (column, colIndex, components) => {
                    const common = <div>
                        {task.heading}&nbsp;&nbsp;
                        {this.props.taskTests.filter((taskTest) => {
                            return taskTest.task === task.id
                        }).length > 0 ? <Button variant={"secondary"}
                                                onClick={(e) => {
                                                    if (!this.props.visibleTaskDetails[task.id]) {
                                                        this.props.showTaskDetails(task.id)
                                                    } else {
                                                        this.props.hideTaskDetails(task.id)
                                                    }
                                                }}>
                            {this.props.visibleTaskDetails[task.id] ? <Icon
                                path={mdiArrowCollapseHorizontal} title={"Collapse"} size={0.8}/> : <Icon
                                path={mdiArrowExpandHorizontal} title={"Expand"} size={0.8}/>}
                        </Button> : null}
                        <Button variant={"secondary"}
                                onClick={(e) => {
                                    this.setState({
                                        sortField: dataField,
                                        sortDirection: task.summary_score_sorting_direction
                                    })
                                }}><Icon
                            path={mdiSort} title={"Sort"} size={0.8}/></Button>
                        {components.sortElement}
                    </div>
                    if (this.props.contest.results.permission_change_contest) {
                        return <div>
                            {common}
                            <Button onClick={(e) => {
                                this.setState({
                                    displayNewTaskTestModal: true,
                                    editTaskTest: this.defaultTaskTest(task.id)
                                })
                            }
                            }>New test</Button>
                            <Button variant={"danger"}
                                    onClick={(e) => {
                                        if (window.confirm("You sure you want to delete the task?")) {
                                            this.props.deleteTask(this.props.contestId, task.id)
                                        }
                                    }}><Icon
                                path={mdiClose} title={"Delete"} size={0.8}/></Button>
                            <Button variant={"secondary"}
                                    onClick={(e) => {
                                        this.setState({displayNewTaskModal: true, editTask: task})
                                    }}><Icon
                                path={mdiPencilOutline} title={"Edit"} size={0.8}/></Button>

                        </div>
                    }
                    return common
                }
            })
        })
        columns.push(contestSummaryColumn)
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

        return <div className={'row'}>
            <div className={"col-12"}>
                <h1>{this.props.contest.results.name}</h1>
                {this.props.contest.results.permission_change_contest ?
                    <Button onClick={(e) => {
                        this.setState({displayNewTaskModal: true, editTask: this.defaultTask()})
                    }}>New task</Button> : null}
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
                                                cellEdit={this.props.contest.results.permission_change_contest ? cellEdit : {}}
                                />
                                <hr/>
                                <ExportCSVButton {...props.csvProps}>Export CSV</ExportCSVButton>
                            </div>
                        )
                    }
                </ToolkitProvider>
            </div>
            <Link to={"../../"}>Contest overview</Link>
            {this.newTaskModal()}
            {this.newTaskTestModal()}
        </div>
    }
}

const
    TaskSummaryResultsTable = connect(mapStateToProps, {
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
    })(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;