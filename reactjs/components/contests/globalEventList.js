import React, {Component} from "react";
import {connect} from "react-redux";
import {
    displayAboutModal,
    displayPastEventsModal,
    hidePastEventsModal, zoomFocusContest
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import Icon from "@mdi/react";
import {mdiAccountDetails, mdiCog, mdiLogin, mdiLogout} from '@mdi/js'
import {Modal, Container, Row, Button, Col} from "react-bootstrap";
import ContestPopupItem from "./contestPopupItem";
import ContestItem from "./contestItem";
import {
    isAndroid,
    isIOS
} from "react-device-detect";
import {Link, withRouter} from "react-router-dom";

export const mapStateToProps = (state, props) => ({
    contests: state.contests,
    pastEventsModalShow: state.displayPastEventsModal,
    myParticipatingContests: state.myParticipatingContests
})
export const mapDispatchToProps = {
    displayPastEventsModal, hidePastEventsModal, displayAboutModal, zoomFocusContest
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

class PastEvents extends Component {
    constructor(props) {
        super(props)
    }

    // let contestBoxes = props.contests.map((contest) => {
    //     return <div key={contest.id + "past_event_div"} style={{paddingTop: "2px", paddingBottom: "4px", width: "300px"}}>
    //         <li key={contest.id + "past_event"} className={"card"}><ContestPopupItem contest={contest}/></li>
    //     </div>
    // })
    render() {
        let contestBoxes = this.props.contests.map((contest) => {
            return <span key={contest.id + "past_event_span"} style={{width: "350px"}}
                         onClick={()=>this.props.handleContestClick(contest)}><ContestItem
                key={"contest" + contest.pk} contest={contest}/></span>
        })

        contestBoxes.reverse()
        return (
            <Modal {...this.props} aria-labelledby="contained-modal-title-vcenter">

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
}

function ContestPopupModal(props) {
    if (!props.contest) {
        return null
    }
    return <Modal {...props} aria-labelledby="contained-modal-title-vcenter">
        <Modal.Header closeButton>
            <Modal.Title id="contained-modal-title-vcenter">
                <h2>{props.contest.name}</h2>
            </Modal.Title>
        </Modal.Header>
        <Modal.Body className="show-grid">
            <Container>
                <ContestPopupItem contest={props.contest} participation={props.participation} link={true}/>
            </Container>
        </Modal.Body>
    </Modal>
}


class ConnectedGlobalEventList extends Component {
    constructor(props) {
        super(props)
        this.state = {displayPopupContest: false, popupContest: null}
    }

    handleContestClick(contest) {
        if (contest.latitude !== 0 && contest.longitude !== 0) {
            this.props.zoomFocusContest(contest.id)
        }
        this.props.history.push("/global/contest_details/"+ contest.id + "/")
    }

    handleManagementClick() {
        window.location.href = document.configuration.managementLink
    }

    getCurrentParticipation(contestId) {
        if (!this.props.myParticipatingContests) return null
        return this.props.myParticipatingContests.find((participation) => {
            return participation.contest.id === contestId
        })
    }

    render() {
        let settingsButton = null
        if (document.configuration.managementLink) {
            settingsButton = <a className={"btn"} href={document.configuration.managementLink}>
                <Icon path={mdiCog} title={"Settings"} size={1.1} color={"white"}/>
            </a>
        }
        let participationButton = null
        if (document.configuration.authenticatedUser) {
            participationButton =
                <Link to={"/participation/"}> <Icon path={mdiAccountDetails} title={"Participation"} size={1.1}
                                                    color={"white"}/>
                </Link>
        }

        let loginButton = null
        if (document.configuration.loginLink) {
            loginButton = <a className={"btn"} href={document.configuration.loginLink}>
                <Icon path={mdiLogin} title={"Login"} size={1.1} color={"white"}/>
            </a>
        }


        let logoutButton = null
        if (document.configuration.logoutLink) {
            logoutButton = <a className={"btn"} href={document.configuration.logoutLink}>
                <Icon path={mdiLogout} title={"Logout"} size={1.1} color={"white"}/>
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
        const popupContest = this.props.contests.find((contest) => {
            return contest.id === this.props.contestDetailsId
        })
        const currentParticipation = this.getCurrentParticipation(this.props.contestDetailsId)
        console.log("Pop-up contest")
        console.log(popupContest)
        console.log(currentParticipation)
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
                              style={{float: "right"}}>{participationButton}{loginButton}{settingsButton}{logoutButton}</span>
                    </div>
                    <div className={"eventListScrolling"}>
                        <div id={"eventMenu"} className={"collapse"}>
                            <div className={"list-group"} id={"ongoing"}>
                                <TimePeriodEventList contests={ongoingEvents}
                                                     onClick={(contest) => this.handleContestClick(contest)}/>
                            </div>
                            <div className={"list-group list-group-root"}>
                                <a href={"#upcoming"}
                                   className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                                   data-toggle={"collapse"}>
                                    <span>Upcoming events</span>
                                    <span style={{"paddingTop": "0.5em"}}
                                          className={"badge badge-dark badge-pill"}>{upcomingEvents.length}</span>
                                </a>
                                <div className={"list-group collapse"} id={"upcoming"}>
                                    <TimePeriodEventList contests={upcomingEvents}
                                                         onClick={(contest) => this.handleContestClick(contest)}/>
                                </div>
                                <a href={"#past"}
                                   className={"list-group-item list-group-item-action list-group-item-secondary d-flex justify-content-between align-items-centre"}
                                   onClick={() => {
                                       this.props.displayPastEventsModal()
                                   }
                                   }>
                            <span>
                            Past events
                                </span>
                                    <span style={{"paddingTop": "0.5em"}}
                                          className={"badge badge-dark badge-pill"}>{earlierEvents.length}</span>
                                </a>
                                {/*<div className={"list-group collapse"} id={"past"}>*/}
                                {/*    <TimePeriodEventList contests={earlierEvents}/>*/}
                                {/*</div>*/}
                                <a
                                    className={"list-group-item list-group-item-action list-group-item-secondary align-items-centre"}
                                    onClick={this.props.displayAboutModal}>About live tracking
                                    {/*<img className={"img-fluid"} style={{width: "50%"}}*/}
                                    {/*     src={"/static/img/about_live_tracking_shadow.png"}/>*/}

                                </a>
                                <div
                                    className={"d-flex justify-content-around list-group-item list-group-item-action list-group-item-secondary align-items-centre"}
                                    style={{paddingBottom: 0, paddingTop: 0}}>
                                    {/*<div className={"p-2"}>*/}
                                    {!isIOS ?
                                        <a target={"_blank"}
                                           href='https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1'><img
                                            alt='Get it on Google Play' style={{height: "45px"}}
                                            src='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png'/></a> : null}
                                    {/*</div>*/}
                                    {/*<div className={"p-2"}>*/}
                                    {!isAndroid ?
                                        <a target={"_blank"}
                                           href="https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&amp;itscg=30200"><img
                                            style={{height: "45px", padding: "8px"}}
                                            src="https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us??size=500x166&amp;releaseDate=1436918400&h=a41916586b4763422c974414dc18bad0"
                                            alt="Download on the App Store"/></a> : null}
                                    {/*</div>*/}
                                </div>

                            </div>
                        </div>
                    </div>
                    {/*<div>*/}
                    {/*    <img src={"/static/img/air_sports.png"}  className={"img-fluid"}/>*/}
                    {/*</div>*/}
                </div>
            </div>

            <PastEvents contests={earlierEvents} show={this.props.pastEventsModalShow}
                        handleContestClick={(contest)=>this.handleContestClick(contest)}
                        dialogClassName="modal-90w" onHide={() => this.props.hidePastEventsModal()}/>
            <ContestPopupModal contest={popupContest} show={popupContest !== undefined} participation={currentParticipation}
                               onHide={() => this.props.history.push("/")}/>
        </div>
    }
}

const GlobalEventList = connect(mapStateToProps, mapDispatchToProps)(withRouter(ConnectedGlobalEventList));
export default GlobalEventList;