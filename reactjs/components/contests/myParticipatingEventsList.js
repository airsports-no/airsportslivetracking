import React, {Component} from "react";
import {connect} from "react-redux";
import {
    fetchMyParticipatingContests, registerForContest, updateContestRegistration
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import {Button, Container, Modal} from "react-bootstrap";
import axios from "axios";
import {teamRankingTable} from "../../utilities";
import {Loading} from "../basicComponents";

axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'

export const mapStateToProps = (state, props) => ({
    myParticipatingContests: state.myParticipatingContests.filter((contestTeam) => {
        return new Date(contestTeam.contest.start_time) >= new Date()
    }),
    loadingMyParticipation: state.loadingMyParticipation,
})
export const mapDispatchToProps = {
    fetchMyParticipatingContests,
    updateContestRegistration
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

    handleChangeClick() {
        this.setState({displayManagementModal: false})
        this.props.updateContestRegistration(this.state.currentParticipation)
    }

    handleWithdrawClick() {
        axios.delete("/api/v1/contests/" + this.state.currentParticipation.contest.id + "/withdraw/").then((res) => {
            this.props.fetchMyParticipatingContests()
            this.setState({displayManagementModal: false})
        }).catch((e) => {
            console.error(e);
        }).finally(() => {
        })
    }

    manageModal() {
        return <Modal onHide={() => this.setState({displayManagementModal: false})}
                      show={this.state.displayManagementModal}
                      aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Manage your participation
                    in {this.state.currentParticipation ? this.state.currentParticipation.contest.name : "error"}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    {this.state.currentParticipation ? <div>
                        <table className={"table"}>
                            <tbody>
                            <tr>
                                <td>Team</td>
                                <td>{teamRankingTable(this.state.currentParticipation.team)}</td>
                            </tr>
                            <tr>
                                <td>Aircraft</td>
                                <td>{this.state.currentParticipation.team.aeroplane.registration}</td>
                            </tr>
                            <tr>
                                <td>Airspeed</td>
                                <td>{this.state.currentParticipation.air_speed} knots</td>
                            </tr>
                            <tr>
                                <td>Club</td>
                                <td>{this.state.currentParticipation.team.club.name}</td>
                            </tr>
                            </tbody>
                        </table>
                        <Button variant={"primary"} onClick={() => this.handleChangeClick()}>Change details</Button>
                        <Button variant={"danger"} onClick={() => this.handleWithdrawClick()}>Withdraw</Button>
                    </div> : null}
                </Container>
            </Modal.Body>
        </Modal>
    }

    render() {
        if (this.props.loadingMyParticipation) {
            return <Loading/>
        }
        return <div className={"eventListScrolling"}>
            <div className={"list-group"} id={"ongoing"}>
                <TimePeriodEventList contests={this.props.myParticipatingContests.map((participation) => {
                    return participation.contest
                })} onClick={(contest) => this.setState({
                    currentParticipation: this.props.myParticipatingContests.find((participation) => {
                        return participation.contest.id === contest.id
                    }),
                    displayManagementModal: true
                })}/>
            </div>
            {this.manageModal()}
            {/*{this.state.currentContest ? this.manageModal() : null}*/}
        </div>
    }
}

const MyParticipatingEventsList = connect(mapStateToProps,
    mapDispatchToProps)(ConnectedMyParticipatingEventsList);
export default MyParticipatingEventsList;