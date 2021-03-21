import React, {Component} from "react";
import {connect} from "react-redux";
import {
    createOrUpdateTask, createOrUpdateTaskTest, deleteTask, deleteTaskTest,
    fetchContestList,
    fetchContestResults,
    fetchContestTeams, fetchTasks, fetchTaskTests,
    hideTaskDetails, putContestSummary, putTaskSummary, putTestResult,
    showTaskDetails
} from "../../actions/resultsService";
import {teamLongForm, teamLongFormText} from "../../utilities";
import BootstrapTable from 'react-bootstrap-table-next';
import paginationFactory from 'react-bootstrap-table2-paginator';
import 'react-bootstrap-table2-toolkit/dist/react-bootstrap-table2-toolkit.min.css';
import "bootstrap/dist/css/bootstrap.min.css"
import {ProgressCircle} from "../contestantProgress";
import {AircraftBadge, ProfileBadge, TeamBadge} from "../teamBadges";
import {Link} from "react-router-dom";

import ToolkitProvider, {CSVExport} from 'react-bootstrap-table2-toolkit';
import cellEditFactory from 'react-bootstrap-table2-editor';
import {Container, Modal, Button, Form} from "react-bootstrap";
import {mdiClose, mdiGoKartTrack, mdiPencilOutline} from "@mdi/js";
import Icon from "@mdi/react";

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
        if (!this.props.results) {
            this.props.fetchContestResults(this.props.contestId)
            this.props.fetchContestTeams(this.props.contestId)
            this.props.fetchTasks(this.props.contestId)
            this.props.fetchTaskTests(this.props.contestId)
        }
        this.state = {
            displayNewTaskModal: false,
            displayNewTaskTestModal: false,
            editTask: this.defaultTask(),
            editTaskTest: this.defaulTaskTest()
        }
    }

    defaultTask() {
        return {
            contest: this.props.contestId,
            summary_score_sorting_direction: "asc",
            name: "",
            heading: "",
        }
    }

    defaulTaskTest(task) {
        return {
            contest: this.props.contest,
            sorting: "asc",
            name: "",
            heading: "",
            index: 0,
            task: task?task:-1
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
                if (task.tasktest_set !== undefined) {
                    task.tasktest_set.map((test) => {
                        data[team]["test_" + test.id.toFixed(0)] = 0
                    })
                }
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
            csvType: "number",
            columnType: "summary"
        }
        let columns = [teamColumn]
        this.props.tasks.map((task) => {
            this.props.taskTests.filter((taskTest) => {
                return taskTest.task === task.id
            }).map((taskTest) => {
                columns.push({
                    dataField: "test_" + taskTest.id.toFixed(0),
                    text: taskTest.heading,
                    headerClasses: "text-muted",
                    sort: true,
                    hidden: !this.props.visibleTaskDetails[task.id],
                    csvType: "number",
                    columnType: "taskTest",
                    taskTest: taskTest.id,
                    headerFormatter: (column, colIndex, components) => {
                        if (this.props.contest.results.permission_change_contest) {
                            return <div>
                                {taskTest.heading}
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
                        return <div>{taskTest.heading}</div>
                    }
                })
            });
            columns.push({
                dataField: "task_" + task.id.toFixed(0),
                text: task.heading,
                sort: true,
                columnType: "task",
                task: task.id,
                events: {
                    onContextMenu: (e, column, columnIndex, row, rowIndex) => {
                        if (!this.props.visibleTaskDetails[task.id]) {
                            this.props.showTaskDetails(task.id.toFixed(0))
                        } else {
                            this.props.hideTaskDetails(task.id.toFixed(0))
                        }
                    }
                },
                hidden: !this.props.visibleTaskDetails[task.id] && this.anyDetailsVisible(),
                csvType: "number",
                headerFormatter: (column, colIndex, components) => {
                    if (this.props.contest.results.permission_change_contest) {
                        return <div>
                            {task.heading}
                            <Button onClick={(e) => {
                                this.setState({
                                    displayNewTaskTestModal: true,
                                    editTaskTest: this.defaulTaskTest(task.id)
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
                    return <div>{task.heading}</div>
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
        const defaultSorted = [{
            dataField: 'summary', // if dataField is not match to any column you defined, it will be ignored.
            order: 'asc'// this.props.contest.results.summary_score_sorting_direction // desc or asc
        }];
        const cellEdit = cellEditFactory({
            mode: 'click',
            blurToSave: true,
            afterSaveCell: (oldValue, newValue, row, column) => {
                const teamId = row.team.id
                if (column.columnType === "summary") {
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
                                <BootstrapTable {...props.baseProps} defaultSorted={defaultSorted}
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
        putTestResult
    })(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;