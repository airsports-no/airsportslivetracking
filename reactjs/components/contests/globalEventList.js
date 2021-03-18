import React, {Component} from "react";
import {connect} from "react-redux";
import {
    displayPastEventsModal,
    hidePastEventsModal
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import Icon from "@mdi/react";
import {mdiCog, mdiLogin, mdiLogout} from '@mdi/js'
import {Modal, Container, Row, Button, Col} from "react-bootstrap";
import ContestPopupItem from "./contestPopupItem";

export const mapStateToProps = (state, props) => ({
    contests: state.contests,
    pastEventsModalShow: state.displayPastEventsModal
})
export const mapDispatchToProps = {
    displayPastEventsModal, hidePastEventsModal
}

function sortContestTimes(a, b) {
    const startTimeA = new Date(a.start_time)
    const finishTimeA = new Date(a.finish_time)
    const startTimeB = new Date(b.start_time)
    const finishTimeB = new Date(b.finish_time)
    if (startTimeA < startTimeB) {
        return -1;
    }
    if (startTimeA > startTimeB) {
        return 1;
    }
    if (finishTimeA < finishTimeB) {
        return -1;
    }
    if (finishTimeA > finishTimeB) {
        return 1;
    }
    return 0;
}

function PastEvents(props) {
    let contestBoxes = props.contests.map((contest) => {
        return <div key={contest.id + "past_event_div"} style={{paddingTop: "2px", paddingBottom: "4px", width: "300px"}}>
            <li key={contest.id + "past_event"} className={"card"}><ContestPopupItem contest={contest}/></li>
        </div>
    })
    contestBoxes.reverse()
    return (
        <Modal {...props} aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Past events
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="show-grid">
                <Container>
                    <ul className={"d-flex flex-wrap justify-content-around"} style={{paddingLeft: "0px"}}>
                        {contestBoxes}
                    </ul>
                </Container>
            </Modal.Body>
        </Modal>
    );
}

class ConnectedGlobalEventList extends Component {
    constructor(props) {
        super(props)
    }

    handleManagementClick() {
        window.location.href = document.configuration.managementLink
    }


    render() {
        let settingsButton = null
        if (document.configuration.managementLink) {
            settingsButton = <a className={"btn"} href={document.configuration.managementLink}>
                <Icon path={mdiCog} title={"Settings"} size={1.1} color={"white"}/>
            </a>
        }


        let loginButton = null
        if (document.configuration.loginLink) {
            loginButton = <a className={"btn"} href={document.configuration.loginLink}>
                <Icon path={mdiLogin} title={"Login"} size={1.1} color={"white"}/>
                {/*<i className={"taskTitle mdi mdi-login"}/>*/}
            </a>
        }


        let logoutButton = null
        if (document.configuration.logoutLink) {
            logoutButton = <a className={"btn"} href={document.configuration.logoutLink}>
                <Icon path={mdiLogout} title={"Logout"} size={1.1} color={"white"}/>
                {/*<i className={"taskTitle mdi mdi-logout"}/>*/}
            </a>
        }

        const now = new Date()
        const upcomingEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (startTime > now) {
                return contest
            }
        }).sort(sortContestTimes)
        const ongoingEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (finishTime > now && startTime < now) {
                return contest
            }
        }).sort(sortContestTimes)
        const earlierEvents = this.props.contests.filter((contest) => {
            const startTime = new Date(contest.start_time)
            const finishTime = new Date(contest.finish_time)
            if (finishTime < now) {
                return contest
            }
        }).sort(sortContestTimes)
        return <div>
            <div className={"globalMapBackdrop"}>
                <div className={"flexWrapper"}>
                    <div
                        className={"titleWrapper"}>
                        <a data-toggle={"collapse"} data-target={"#eventMenu"}
                           style={{paddingLeft: "14px", paddingRight: "12px"}}>
                            <i className={"eventTitle mdi mdi-menu"} id={'menuButton'}/>
                        </a>
                        <a href={"#"} className={'eventTitle taskTitleName'} data-toggle={"collapse"}
                           data-target={"#eventMenu"}>Events</a>

                        <span className={"eventTitle"}
                              style={{float: "right"}}>{loginButton}{settingsButton}{logoutButton}</span>
                    </div>
                    <div className={"eventListScrolling"}>
                        <div id={"eventMenu"} className={"collapse"}>
                            <div className={"list-group"} id={"ongoing"}>
                                <TimePeriodEventList contests={ongoingEvents}/>
                            </div>
                            <div className={"list-group list-group-root"}>
                                <a href={"#upcoming"}
                                   className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                                   data-toggle={"collapse"}>
                                    <span><i className={"mdi mdi-keyboard-arrow-right"}/>Upcoming events</span>
                                    <span style={{"paddingTop": "0.5em"}}
                                          className={"badge badge-dark badge-pill"}>{upcomingEvents.length}</span>
                                </a>
                                <div className={"list-group collapse"} id={"upcoming"}>
                                    <TimePeriodEventList contests={upcomingEvents}/>
                                </div>
                                <a href={"#past"}
                                   className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                                   onClick={() => this.props.displayPastEventsModal()}>
                            <span>
                            Past events
                                </span>
                                    <span style={{"paddingTop": "0.5em"}}
                                          className={"badge badge-dark badge-pill"}>{earlierEvents.length}</span>
                                </a>
                                {/*<div className={"list-group collapse"} id={"past"}>*/}
                                {/*    <TimePeriodEventList contests={earlierEvents}/>*/}
                                {/*</div>*/}
                            </div>
                        </div>
                    </div>
                    {/*<div>*/}
                    {/*    <img src={"/static/img/air_sports.png"}  className={"img-fluid"}/>*/}
                    {/*</div>*/}
                </div>
            </div>
            <PastEvents contests={earlierEvents} show={this.props.pastEventsModalShow}
                        dialogClassName="modal-90w" onHide={() => this.props.hidePastEventsModal()}/>
        </div>
    }
}

const GlobalEventList = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalEventList);
export default GlobalEventList;