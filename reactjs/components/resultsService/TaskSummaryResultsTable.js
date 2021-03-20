import React, {Component} from "react";
import {connect} from "react-redux";
import {
    createNewTask, createNewTaskTest, deleteTask, deleteTaskTest,
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
import {mdiClose, mdiGoKartTrack} from "@mdi/js";
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
            taskName: null,
            taskId: null,
            taskTestName: null,
            task: null,
            displayNewTaskModal: false,
            displayNewTaskTestModal: false
        }
    }

    componentDidUpdate(prevProps) {
    }

    handleTaskNameChange(e) {
        this.setState({taskName: e.target.value})
    }

    handleTaskTestNameChange(e) {
        this.setState({taskTestName: e.target.value})
    }

    handleTaskChange(e) {
        this.setState({task: e.target.value})
    }


    createNewTask() {
        this.setState({displayNewTaskModal: false})
        this.props.createNewTask(this.props.contestId, this.state.taskName)
    }

    createNewTaskTest() {
        if (this.state.task !== -1) {
            this.setState({displayNewTaskTestModal: false})
            this.props.createNewTaskTest(this.props.contestId, this.state.task, this.state.taskTestName)
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
                            <Form.Control type={"text"} onChange={(e) => this.handleTaskNameChange(e)}/>
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
                            <Form.Control as={"select"} onChange={(e) => this.handleTaskChange(e)}>
                                <option key={-1} value={-1}>--</option>
                                {this.props.tasks.map((task) => {
                                    return <option key={task.id} value={task.id}>{task.name}</option>
                                })}
                            </Form.Control>
                            <Form.Label>Test name</Form.Label>
                            <Form.Control type={"text"} onChange={(e) => this.handleTaskTestNameChange(e)}/>
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
                        return <div>
                            {taskTest.heading}
                            <Button variant={"danger"}
                                    onClick={(e) => this.props.deleteTaskTest(this.props.contestId, taskTest.id)}><Icon
                                path={mdiClose} title={"Delete"} size={1}/></Button>
                        </div>

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
                    return <div>
                        {task.heading}
                        <Button onClick={(e) => this.setState({displayNewTaskTestModal: true, task: task.id})}>New
                            test</Button>
                        <Button variant={"danger"}
                                onClick={(e) => this.props.deleteTask(this.props.contestId, task.id)}><Icon
                            path={mdiClose} title={"Delete"} size={1}/></Button>
                    </div>
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
        console.log(c)
        console.log(d)
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
                <Button onClick={(e) => this.setState({displayNewTaskModal: true})}>New task</Button>
                <ToolkitProvider
                    keyField="key"
                    data={d}
                    columns={c}
                    exportCSV
                >
                    {
                        props => (
                            <div>
                                <BootstrapTable {...props.baseProps} defaultSorted={defaultSorted} cellEdit={cellEdit}
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
        createNewTask,
        createNewTaskTest,
        deleteTask,
        deleteTaskTest,
        putContestSummary,
        putTaskSummary,
        putTestResult
    })(ConnectedTaskSummaryResultsTable);
export default TaskSummaryResultsTable;