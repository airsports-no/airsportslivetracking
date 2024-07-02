import React, {Component} from "react";
import {connect} from "react-redux";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import {
    createOrUpdateTask, createOrUpdateTaskTest, deleteTask, deleteTaskTest,
    fetchContestResults,
    hideAllTaskDetails,
    hideTaskDetails, putContestSummary, putTaskSummary, putTestResult, resultsData,
    showTaskDetails, tasksData, teamsData, testsData
} from "../../actions/resultsService";
import {teamLongForm, teamLongFormText, teamRankingTable, withParams} from "../../utilities";
import "bootstrap/dist/css/bootstrap.min.css"
import {Link} from "react-router-dom";

import {Container, Modal, Button, Form} from "react-bootstrap";
import {
    mdiChevronLeft, mdiChevronRight,
    mdiClose, mdiDeleteForever, mdiEarth,
    mdiPencilOutline
} from "@mdi/js";
import Icon from "@mdi/react";
import {sortCaret, sortFunc} from "./resultsTableUtilities";
import {Loading} from "../basicComponents";
import Navbar from "../navbar";
import {EditableCell, ResultsServiceTable} from "./resultsServiceTable";


const mapStateToProps = (state, props) => ({
    contest: state.contestResults[props.params.contestId],
    contestError: state.contestResultsErrors[props.params.contestId],
    tasks: state.tasks[props.params.contestId],
    taskTests: state.taskTests[props.params.contestId],
    teams: state.teams,
    visibleTaskDetails: state.visibleTaskDetails
})



class ConnectedTaskSummaryResultsTable extends Component {
    constructor(props) {
        super(props)
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
        this.props.fetchContestResults(this.props.params.contestId)
        this.timeout = setTimeout(() => this.periodicallyFetchResults(), 300000)
    }

    componentDidUpdate(prevProps) {
        if (this.props.params.task && !prevProps.tasks && this.props.tasks) {
            const task = this.props.tasks.find((task) => {
                return task.id === parseInt(this.props.params.task)
            })
            this.expandTask(task)
        }
    }

    deleteResultsTableLine(contestId, teamId) {
        let url = document.configuration.contestDeleteTeamResultsUrl(contestId)
        $.ajax({
            url: url,
            datatype: 'json',
            data: {team_id: teamId},
            method: "POST",
            cache: false,
            success: value => {
                this.props.fetchContestResults(contestId)
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
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/contestresults/" + this.props.params.contestId + "/")
        this.client.onopen = () => {
            console.log("Client connected")
            clearTimeout(this.connectInterval)
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            if (data.type === "contest.teams") {
                this.props.teamsData(data.teams, this.props.params.contestId)
            }
            if (data.type === "contest.tasks") {
                this.props.tasksData(data.tasks, this.props.params.contestId)
            }
            if (data.type === "contest.tests") {
                this.props.testsData(data.tests, this.props.params.contestId)
            }
            if (data.type === "contest.results") {
                data.results.permission_change_contest = this.props.contest.results.permission_change_contest
                this.props.resultsData(data.results, this.props.params.contestId)
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
            contest: this.props.params.contestId,
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
        if (this.props.params.task) {
            this.props.navigate("/resultsservice/" + this.props.params.contestId + "/taskresults/")
        }
    }

    createNewTask() {
        this.setState({displayNewTaskModal: false})
        this.props.createOrUpdateTask(this.props.params.contestId, this.state.editTask)
    }

    createNewTaskTest() {
        if (this.state.editTaskTest.task !== -1) {
            this.setState({displayNewTaskTestModal: false})
            this.props.createOrUpdateTaskTest(this.props.params.contestId, this.state.editTaskTest)
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
        this.props.createOrUpdateTask(this.props.params.contestId, task)
        this.props.createOrUpdateTask(this.props.params.contestId, switchingWith)
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
        this.props.createOrUpdateTask(this.props.params.contestId, task)
        this.props.createOrUpdateTask(this.props.params.contestId, switchingWith)
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
        this.props.createOrUpdateTaskTest(this.props.params.contestId, test)
        this.props.createOrUpdateTaskTest(this.props.params.contestId, switchingWith)
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
        this.props.createOrUpdateTaskTest(this.props.params.contestId, test)
        this.props.createOrUpdateTaskTest(this.props.params.contestId, switchingWith)
    }


    buildData() {
        let data = {}
        // Make sure that each team has a row The gaps if it has any points, even if it is not registered
        this.props.contest.results.contestsummary_set.map((summary) => {
            let team = summary.team
            data[team.id] = {
                contestSummary: "-",
                team: team,
                key: team.id + "_" + this.props.params.contestId,
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
                key: team + "_" + this.props.params.contestId,
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
            Header: "Team",
            accessor: (row, index) => {
                let clearButton = null
                if (this.props.contest.results.permission_change_contest) {
                    clearButton = <a href={"#"} style={{float: "right"}}
                                     onClick={(e) => {
                                         e.stopPropagation()
                                         let confirmation = confirm("Are you sure you want to delete?")
                                         if (confirmation) {
                                             this.deleteResultsTableLine(this.props.params.contestId, row.team.id)
                                         }
                                     }}><Icon
                        path={mdiDeleteForever} title={"Delete team"} size={0.7}/></a>
                }
                return <div className={"align-middle crew-name"}>{clearButton}{teamRankingTable(row.team)}</div>
            },
            editable: false,
            disableFilters: true,
            disableSortBy: true,
        }

        const contestSummaryColumn = {
            Header: this.props.contest.results.permission_change_contest ? <span>Σ<br/>&nbsp;</span> : "Σ",
            accessor: "contestSummary",
            sort: true,
            Cell: !this.props.contest.results.autosum_scores && this.props.contest.results.permission_change_contest ? EditableCell : ({value}) => String(value),
            classes: "number-right " + (!this.props.contest.results.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : ""),
            sortDirection: this.props.contest.results.summary_score_sorting_direction,
            disableFilters: true,
            columnType: "contestSummary",
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
                    id: dataField,
                    accessor: dataField,
                    Cell: !taskTest.navigation_task && this.props.contest.results.permission_change_contest ? EditableCell : ({value}) => String(value),
                    Header: () => {
                        let header = <span>{taskTest.heading}</span>
                        let privilege_break = null

                        if (taskTest.navigation_task_link) {
                            header =
                                <span>{taskTest.heading}<a
                                    href={taskTest.navigation_task_link}><Icon
                                    path={mdiEarth} size={0.7}/></a></span>
                        }
                        let privileged = null
                        let move = null
                        if (this.props.contest.results.permission_change_contest) {
                            privilege_break = <span><br/>&nbsp;</span>

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
                                               this.props.deleteTaskTest(this.props.params.contestId, taskTest.id)
                                           }
                                       }}><Icon
                                        path={mdiClose} title={"Delete"} size={0.7}/></a> : null}
                                    </span>
                        }
                        return <span>{header}{privilege_break}{privileged}{move}</span>
                    },
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    disableFilters: true,
                    classes: "number-right " + (this.props.contest.results.permission_change_contest ? "editableCell" : ""),
                    columnType: "taskTest",
                    taskTest: taskTest.id,
                })
            });
            const dataField = "task_" + task.id.toFixed(0)
            columns.push({
                id: dataField,
                accessor: dataField,
                Cell: !task.autosum_scores && this.props.contest.results.permission_change_contest ? EditableCell : ({value}) => String(value),
                Header: () => {
                    let privilege_break = null
                    let privileged = null
                    let move = null
                    const common = <span>
                        {task.heading}
                    </span>
                    if (this.props.contest.results.permission_change_contest) {
                        privilege_break = <span><br/>&nbsp;</span>
                        if (!this.state.zoomedTask) {
                            move = <span style={{position: "absolute", bottom: "0", right: "0"}}>
                                {taskIndex > 0 ?
                                    <a href={"#"} onClick={(e) => this.moveTaskLeft(e, task.id)}><Icon
                                        path={mdiChevronLeft} size={0.7}/></a> : null}
                                {taskIndex < this.props.tasks.length - 1 ?
                                    <a href={"#"} onClick={(e) => this.moveTaskRight(e, task.id)}><Icon
                                        path={mdiChevronRight} size={0.7}/></a> : null}
                            </span>
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
                                           this.props.deleteTask(this.props.params.contestId, task.id)
                                       }
                                   }}><Icon
                                    path={mdiClose} title={"Delete"} size={0.7}/></a> : null}
                            </span>
                    }
                    return <span>{this.props.visibleTaskDetails[task.id] ?
                        <a href={"#"}
                           onClick={(e) => {
                               e.stopPropagation()
                               this.collapseTask(task)
                           }}
                        >{common} (Σ)</a> : <a href={"#"}
                                               onClick={(e) => {
                                                   e.stopPropagation()
                                                   this.expandTask(task)
                                               }}
                        >{common} (Σ)</a>}{privilege_break}{privileged}
                        {move}
                    </span>
                },

                columnType: "task",
                disableFilters: true,
                classes: "number-right " + (!task.autosum_scores && this.props.contest.results.permission_change_contest ? "editableCell" : ""),
                task: task.id,
                hidden: !this.props.visibleTaskDetails[task.id] && this.anyDetailsVisible(),
            })
        })
        return columns
    }

    updateMyData(row, column, newValue) {
        const teamId = row.original.team.id
        if (newValue === undefined || newValue.length === 0) {
            newValue = 0
        }
        if (column.columnType === "contestSummary") {
            this.props.putContestSummary(this.props.params.contestId, teamId, newValue)
        } else if (column.columnType === "task") {
            this.props.putTaskSummary(this.props.params.contestId, teamId, column.task, newValue)
        } else if (column.columnType === "taskTest") {
            this.props.putTestResult(this.props.params.contestId, teamId, column.taskTest, newValue)
        }
    }


    render() {
        if (this.props.contestError) {
            return <div>
                <Navbar/>
                <div className={"container-xl"}>
                    <h4 className="alert alert-warning" role="alert">Failed loading
                        contest: {this.props.contestError.responseJSON?this.props.contestError.responseJSON.detail:"Unknown"}</h4>
                    <p>Contact support or visit <a
                        href={'https://home.airsports.no/faq/#contest-results-are-not-found'}>our FAQ</a> for
                        more
                        details.</p>
                </div>
            </div>
        }
        if (!this.props.teams || !this.props.contest || !this.props.tasks || !this.props.taskTests) return <Loading/>
        const c = this.buildColumns()
        const d = this.buildData()

        return <div>
            <Navbar/>
            <div className={"container-xl"}>
                <div className={"row results-table"}>
                    <div className={"col-2"}>
                        <h2 className={"results-table-contest-name"} style={{float: "left"}}><Link
                            className={"text-dark"}
                            to={"/resultsservice/"}>Results</Link></h2>
                    </div>
                    <div className={"col-8"} style={{textAlign: 'center'}}>
                        {
                            this.state.zoomedTask ?
                                <h3 className={"results-table-contest-name"}><a
                                    href={"#"} className={"text-dark"}
                                    onClick={() => this.collapseTask(this.state.zoomedTask)}>{this.props.contest.results.name}</a><br/>
                                    <b>{this.state.zoomedTask.name}</b>
                                </h3>
                                :
                                <h3 className={"results-table-contest-name"}>
                                    <b>{this.props.contest.results.name}</b>
                                </h3>
                        }
                    </div>
                    <div className={"col-2"}>
                        {
                            this.state.zoomedTask ?

                                this.props.contest.results.permission_change_contest ?
                                    <Button onClick={(e) => {
                                        this.setState({
                                            displayNewTaskTestModal: true,
                                            editTaskTest: this.defaultTaskTest(this.state.zoomedTask.id),
                                            editMode: "new"
                                        })
                                    }
                                    } style={{float: "right"}}>New test</Button> : null
                                :
                                this.props.contest.results.permission_change_contest ?
                                    <Button style={{float: "right"}} onClick={(e) => {
                                        this.setState({
                                            displayNewTaskModal: true,
                                            editTask: this.defaultTask(),
                                            editMode: "new"
                                        })
                                    }}>New task</Button> : null
                        }
                    </div>
                </div>
                <div className={"results-table"}>
                    <div className={""}>
                        <div>
                            <ResultsServiceTable data={d} columns={c}
                                                 updateMyData={this.updateMyData.bind(this)}
                                                 className={"table table-striped table-condensed table-dark bg-dark-transparent table-bordered"}
                                                 initialState={{
                                                     sortBy: [
                                                         {
                                                             id: "contestSummary",
                                                             desc: this.props.contest.results.summary_score_sorting_direction === "desc"
                                                         }
                                                     ]
                                                 }}
                            />
                        </div>
                    </div>
                    <div className={"alert alert-info alert-dismissable fade show"} style={{marginTop: "20px"}}>
                        <button type="button" className="close" data-dismiss="alert"
                                aria-hidden="true">&#215;</button>
                        <h4 className="alert-heading">About the results table</h4>
                        Contest results consists of one or more tasks, and each task contains one or more tests.
                        The
                        initial
                        view shows the summary score for each task in the contest. By clicking on the task name
                        you
                        can zoom into the individual test results within the task. Zoom out by clicking on the
                        titles
                        above the table or the same task name in the rightmost column. For instance, a precision
                        navigation
                        task
                        will consist of three tests; a planning test, a navigation test, and an observation
                        test. The
                        total
                        score of these three tests make up the score for the task.
                        {this.props.contest.results.permission_change_contest ? <div>
                            <hr/>
                            <a className={"alert-link"} href={"/static/documents/contest_results_admin.pdf"}>Administration
                                how-to guide</a>
                        </div> : null}

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
            showTaskDetails,
            hideTaskDetails,
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
export default withParams(TaskSummaryResultsTable);