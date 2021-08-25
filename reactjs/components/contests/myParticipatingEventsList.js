import React, {Component} from "react";
import {connect} from "react-redux";
import {
    fetchMyParticipatingContests,
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import {Button, Container, Modal} from "react-bootstrap";
import axios from "axios";
import {formatDate, formatTime, teamRankingTable} from "../../utilities";
import {Loading} from "../basicComponents";
import SelfRegistrationForm from "../navigationTaskStartForm";
import {withRouter} from "react-router-dom";
import {mdiShare} from "@mdi/js";
import Icon from "@mdi/react";

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
}


class ConnectedMyParticipatingEventsList extends Component {
    constructor(props) {
        super(props)
        this.state = {errorMessage: null}
    }

    componentDidMount() {
        this.props.fetchMyParticipatingContests()
    }

    getCurrentParticipation(participationId) {
        return this.props.myParticipatingContests.find((participation) => {
            return participation.id === participationId
        })
    }

    getNavigationTask(navigationTaskId) {
        return this.props.currentParticipation.contest.navigationtask_set.find((task) => {
            return task.pk === navigationTaskId
        })
    }

    handleChangeClick(currentParticipation) {
        this.props.history.push("/participation/" + currentParticipation.contest.id + "/register/")
    }

    handleEnterClick(currentParticipation, navigationTask) {
        this.props.history.push("/participation/myparticipation/" + currentParticipation.id + "/signup/" + navigationTask.pk + "/")
    }

    handleWithdrawClick(currentParticipation) {
        this.setState({errorMessage: null})
        axios.delete("/api/v1/contests/" + currentParticipation.contest.id + "/withdraw/").then((res) => {
            this.props.fetchMyParticipatingContests()
            this.props.history.push("/participation/")
        }).catch((e) => {
            console.error(e);
            this.setState({errorMessage: e.response.data[0]})
        }).finally(() => {
        })
    }

    handleWithdrawTaskClick(currentParticipation, navigationTask) {
        this.setState({errorMessage: null})
        axios.delete("/api/v1/contests/" + currentParticipation.contest.id + "/navigationtasks/" + navigationTask.pk + "/contestant_self_registration/").then((res) => {
            this.props.fetchMyParticipatingContests()
            this.props.history.push("/participation/myparticipation/" + currentParticipation.id + "/")
        }).catch((e) => {
            console.error(e);
        }).finally(() => {
        })
    }

    hideModal() {
        this.props.history.push("/participation/")
    }

    manageModal() {
        if (!this.props.currentParticipation) {
            return null
        }
        const taskRows = this.props.currentParticipation.contest.navigationtask_set.sort((a, b) => (a.start_time > b.start_time) ? 1 : ((b.start_time > a.start_time) ? -1 : 0)).reverse().map((task) => {
            const startingPointTime = task.future_contestants.length > 0 ? new Date(new Date(task.future_contestants[0].takeoff_time).getTime() + task.future_contestants[0].minutes_to_starting_point * 60000) : null
            return <tr key={task.pk}>
                <td>{task.name}</td>
                <td>{task.future_contestants.length > 0 ?
                    <div>
                        {/*<a href={task.future_contestants[0].default_map_url}>Map (slow)</a>*/}
                        <div>Starting point
                            time: {formatDate(startingPointTime) + " " + formatTime(startingPointTime)}</div>

                    </div> : null}</td>
                <td>
                    {this.props.currentParticipation.can_edit ?
                        task.future_contestants.length > 0 ?
                            <Button variant={"danger"}
                                    onClick={() => this.handleWithdrawTaskClick(this.props.currentParticipation, task)}>Cancel
                                flight</Button> :
                            <Button variant={"primary"}
                                    onClick={() => this.handleEnterClick(this.props.currentParticipation, task)}>Schedule
                                flight</Button>
                        : null}
                    <a style={{float: "right"}} href={task.tracking_link}><Icon path={mdiShare}
                                                                                title={"Direct link"}
                                                                                size={1.5}
                                                                                color={"black"}/></a>
                </td>
            </tr>
        })
        let modalBody = null
        if (this.props.loadingMyParticipation) {
            modalBody = <Loading/>
        } else if (this.props.navigationTaskId) {
            const navigationTask = this.getNavigationTask(this.props.navigationTaskId)
            modalBody = <SelfRegistrationForm navigationTask={navigationTask}
                                              participation={this.props.currentParticipation}/>
        } else if (this.props.currentParticipation) {
            modalBody = <div>
                {taskRows.length > 0 ? <div>
                    <table className={"table table-condensed"}>
                        <tbody>
                        {taskRows}
                        </tbody>
                    </table>
                </div> : null}
                <h4>Team details</h4>
                <table className={"table"}>
                    <tbody>
                    <tr>
                        <td>Team</td>
                        <td>{teamRankingTable(this.props.currentParticipation.team)}</td>
                    </tr>
                    <tr>
                        <td>Aircraft</td>
                        <td>{this.props.currentParticipation.team.aeroplane.registration}</td>
                    </tr>
                    <tr>
                        <td>Airspeed</td>
                        <td>{this.props.currentParticipation.air_speed} knots</td>
                    </tr>
                    <tr>
                        <td>Club</td>
                        <td>{this.props.currentParticipation.team.club.name}</td>
                    </tr>
                    </tbody>
                </table>
                {this.props.currentParticipation.can_edit ? <div>
                    <Button variant={"primary"} onClick={() => this.handleChangeClick(this.props.currentParticipation)}>Change
                        details</Button>
                    <Button variant={"danger"}
                            onClick={() => this.handleWithdrawClick(this.props.currentParticipation)}>Withdraw</Button>

                </div> : <b>Only pilots can edit contest participation</b>}
                {this.state.errorMessage ? <div className={"alert alert-danger alert-dismissible fade show"}
                                                role={"alert"}>{this.state.errorMessage}
                    <button type="button" className="close" data-dismiss="alert" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div> : null}
            </div>
        }
        return <Modal onHide={() => this.hideModal()}
                      show={this.props.currentParticipation != null}
                      aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Manage your participation
                    in {this.props.currentParticipation ? this.props.currentParticipation.contest.name : "error"}
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
                })} onClick={(contest) => {
                    const currentParticipation = this.props.myParticipatingContests.find((participation) => {
                        return participation.contest.id === contest.id
                    }).id
                    this.props.history.push("/participation/myparticipation/" + currentParticipation + "/")
                }}/>
            </div> : <Loading/>}
        </div>
    }
}

const MyParticipatingEventsList = connect(mapStateToProps,
    mapDispatchToProps)(withRouter(ConnectedMyParticipatingEventsList));
export default MyParticipatingEventsList;