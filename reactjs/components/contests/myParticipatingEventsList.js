import React, {Component} from "react";
import {connect} from "react-redux";
import {
    fetchMyParticipatingContests,
    registerForContest,
    selfRegisterTask,
    selfRegisterTaskReturn,
    updateContestRegistration
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import {Button, Container, Modal} from "react-bootstrap";
import axios from "axios";
import {teamRankingTable} from "../../utilities";
import {Loading} from "../basicComponents";
import SelfRegistrationForm from "../navigationTaskStartForm";

axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'

export const mapStateToProps = (state, props) => ({
    myParticipatingContests: state.myParticipatingContests.filter((contestTeam) => {
        return new Date(contestTeam.contest.finish_time) >= new Date()
    }),
    loadingMyParticipation: state.loadingMyParticipation,
    currentSelfRegisterTask: state.currentSelfRegisterTask,
    currentSelfRegisterParticipation: state.currentSelfRegisterParticipation
})
export const mapDispatchToProps = {
    fetchMyParticipatingContests,
    updateContestRegistration,
    selfRegisterTask,
    selfRegisterTaskReturn
}


class ConnectedMyParticipatingEventsList extends Component {
    constructor(props) {
        super(props)
        this.state = {
            displayManagementModal: false,
            currentParticipation: null
        }
    }

    componentDidMount() {
        this.props.fetchMyParticipatingContests()
    }

    handleChangeClick(currentParticipation) {
        this.setState({displayManagementModal: false})
        this.props.updateContestRegistration(currentParticipation)
    }

    handleEnterClick(currentParticipation, navigationTask) {
        this.props.selfRegisterTask(currentParticipation, navigationTask)
    }

    handleWithdrawClick(currentParticipation) {
        axios.delete("/api/v1/contests/" + currentParticipation.contest.id + "/withdraw/").then((res) => {
            this.setState({displayManagementModal: false, currentParticipation: null})
            this.props.fetchMyParticipatingContests()
        }).catch((e) => {
            console.error(e);
        }).finally(() => {
        })
    }

    handleWithdrawTaskClick(contest, navigationTask) {
        axios.delete("/api/v1/contests/" + contest.id + "/navigationtasks/" + navigationTask.pk + "/contestant_self_registration/").then((res) => {
            this.props.fetchMyParticipatingContests()
        }).catch((e) => {
            console.error(e);
        }).finally(() => {
        })
    }

    hideModal() {
        this.setState({displayManagementModal: false})
        this.props.selfRegisterTaskReturn()
    }

    manageModal() {
        if (!this.state.currentParticipation) {
            return null
        }
        const currentParticipation = this.props.myParticipatingContests.find((participation) => {
            return participation.id === this.state.currentParticipation
        })
        const taskRows = currentParticipation.contest.navigationtask_set.sort((a, b) => (a.start_time > b.start_time) ? 1 : ((b.start_time > a.start_time) ? -1 : 0)).reverse().map((task) => {
            return <tr key={task.pk}>
                <td>{task.name}</td>
                <td>{task.future_contestants.length > 0 ?
                    <div><a target={"_blank"} href={task.future_contestants[0].default_map_url}>Navigation map</a>
                        <div>Starting point
                            time: {new Date(new Date(task.future_contestants[0].takeoff_time).getTime() + task.future_contestants[0].minutes_to_starting_point * 60000).toLocaleString()}</div>

                    </div> : null}</td>
                <td>
                    {currentParticipation.can_edit ?
                        task.future_contestants.length > 0 ?
                            <Button variant={"danger"}
                                    onClick={() => this.handleWithdrawTaskClick(currentParticipation.contest, task)}>Cancel
                                flight</Button> :
                            <Button variant={"primary"}
                                    onClick={() => this.handleEnterClick(currentParticipation, task)}>Start
                                flight</Button>
                        : null}
                </td>
            </tr>
        })
        let modalBody = null
        if (this.props.loadingMyParticipation) {
            modalBody = <Loading/>
        } else if (this.props.currentSelfRegisterTask) {
            modalBody = <SelfRegistrationForm navigationTask={this.props.currentSelfRegisterTask}
                                              participation={this.props.currentSelfRegisterParticipation}/>
        } else if (currentParticipation) {
            modalBody = <div>
                <table className={"table"}>
                    <tbody>
                    <tr>
                        <td>Team</td>
                        <td>{teamRankingTable(currentParticipation.team)}</td>
                    </tr>
                    <tr>
                        <td>Aircraft</td>
                        <td>{currentParticipation.team.aeroplane.registration}</td>
                    </tr>
                    <tr>
                        <td>Airspeed</td>
                        <td>{currentParticipation.air_speed} knots</td>
                    </tr>
                    <tr>
                        <td>Club</td>
                        <td>{currentParticipation.team.club.name}</td>
                    </tr>
                    </tbody>
                </table>
                {currentParticipation.can_edit ? <div>
                    <Button variant={"primary"} onClick={() => this.handleChangeClick(currentParticipation)}>Change
                        details</Button>
                    <Button variant={"danger"}
                            onClick={() => this.handleWithdrawClick(currentParticipation)}>Withdraw</Button>

                </div> : <b>Only pilots can edit contest participation</b>}
                {taskRows.length > 0 ? <div>
                    <h3>Available tasks</h3>
                    <table className={"table table-condensed"}>
                        <tbody>
                        {taskRows}
                        </tbody>
                    </table>
                </div> : null}
            </div>
        }
        return <Modal onHide={() => this.hideModal()}
                      show={this.state.displayManagementModal}
                      aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Manage your participation
                    in {this.state.currentParticipation ? currentParticipation.contest.name : "error"}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    {modalBody}
                </Container>
            </Modal.Body>
        </Modal>
    }

    render() {
        return <div className={"eventListScrolling"}>
            {this.manageModal()}

            {!this.props.loadingMyParticipation ? <div className={"list-group"} id={"ongoing"}>
                <TimePeriodEventList contests={this.props.myParticipatingContests.map((participation) => {
                    return participation.contest
                })} onClick={(contest) => this.setState({
                    currentParticipation: this.props.myParticipatingContests.find((participation) => {
                        return participation.contest.id === contest.id
                    }).id,
                    displayManagementModal: true
                })}/>
            </div> : <Loading/>}
            {/*{this.state.currentContest ? this.manageModal() : null}*/}
        </div>
    }
}

const MyParticipatingEventsList = connect(mapStateToProps,
    mapDispatchToProps)(ConnectedMyParticipatingEventsList);
export default MyParticipatingEventsList;