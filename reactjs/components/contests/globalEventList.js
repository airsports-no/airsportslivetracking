import React, {Component} from "react";
import {connect} from "react-redux";
import {
    displayAboutModal, displayEventSearchModal, hideEventSearchModal, zoomFocusContest
} from "../../actions";
import TimePeriodEventList from "./timePeriodEventList";
import Icon from "@mdi/react";
import {mdiAccountDetails, mdiCog, mdiLogin, mdiLogout, mdiMapSearch} from '@mdi/js'
import {Modal, Container} from "react-bootstrap";
import ContestPopupItem from "./contestPopupItem";
import {
    isAndroid, isIOS
} from "react-device-detect";
import {Link, Navigate} from "react-router-dom";
import axios from "axios";
import {sortStartAndFinishTimes} from "./utilities";
import {withParams} from "../../utilities";
import {EventTable} from "./eventTable";
import OngoingNavigationTicker from "./ongoingNavigationTicker";
import {Loading} from "../basicComponents";

export const mapStateToProps = (state, props) => ({
    contests: state.contests,
    eventSearchModalShow: state.displayEventSearchModal,
    myParticipatingContests: state.myParticipatingContests,
    globalMapVisibleContests: state.globalMapVisibleContests
})
export const mapDispatchToProps = {
    displayEventSearchModal: displayEventSearchModal,
    hideEventSearchModal: hideEventSearchModal,
    displayAboutModal,
    zoomFocusContest
}

class EventSearchModal extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return (<Modal {...this.props} aria-labelledby="contained-modal-title-vcenter">

            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Find contests
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    <div className={""}>
                        <EventTable contests={this.props.contests}
                                    handleContestClick={this.props.handleContestClick}/>
                    </div>
                </Container>
            </Modal.Body>
        </Modal>);
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

    componentDidUpdate(prevProps) {
        if (this.props.contestPopupId && this.props.contestPopupId !== prevProps.contestPopupId) {
            this.props.zoomFocusContest(this.props.contestPopupId)
        }
    }

    handleContestClick(contest) {
        this.props.hideEventSearchModal()
        this.props.navigate("/global/contest_details/" + contest.id + "/")
    }

    handleContestOnMapClick(contest) {
        this.props.zoomFocusContest(contest.id)
    }

    getCurrentParticipation(contestId) {
        if (!this.props.myParticipatingContests) return null
        return this.props.myParticipatingContests.find((participation) => {
            return participation.contest.id === contestId
        })
    }

    render() {
        let settingsButton = null
        const searchButton = <a className={"btn"} onClick={() => this.props.displayEventSearchModal()}><Icon
            path={mdiMapSearch} size={1.1} color={"white"}/></a>
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
            logoutButton = <a className={"btn"} onClick={()=>axios({
            method: "post",
            url: document.configuration.logoutLink,
        }).then((res) => {window.location.href="/"})}>
                <Icon path={mdiLogout} title={"Logout"} size={1.1} color={"white"}/>
            </a>
        }
        const visibleEvents = this.props.contests.filter((contest) => {
            return this.props.globalMapVisibleContests.includes(contest.id)
        }).sort(sortStartAndFinishTimes)
        const popupContest = this.props.contests.find((contest) => {
            return contest.id === this.props.contestDetailsId
        })
        const currentParticipation = this.getCurrentParticipation(this.props.contestDetailsId)
        return <div>
            <div className={"globalMapBackdrop"}>
                <div className={"flexWrapper"}>
                    <div
                        className={"titleWrapper"}>
                        <a data-toggle={"collapse"} data-target={"#ongoing"}
                           style={{paddingLeft: "14px", paddingRight: "12px"}}>
                            <i className={"eventTitle mdi mdi-menu"} id={'menuButton'}/>
                        </a>
                        <a href={"#"} className={'eventTitle taskTitleName'} data-toggle={"collapse"}
                           data-target={"#eventMenu"}>Events</a>

                        <span className={"eventTitle"}
                              style={{float: "right"}}>{searchButton}{participationButton}{loginButton}{settingsButton}{logoutButton}</span>
                    </div>
                    <div className={"eventListScrolling"}>
                        <div id={"eventMenu"}>
                            <div className={"list-group"} id={"ongoing"}>
                                <a className={"list-group-item list-group-item-secondary list-group-item-action"}
                                   onClick={() => this.props.displayEventSearchModal()}><Icon
                                    path={mdiMapSearch} size={1.1} color={"black"}/> <b>Search</b></a>
                                {this.props.contests.length > 0 ? <OngoingNavigationTicker/> : <div
                                    className={"list-group-item list-group-item-secondary list-group-item-action"}
                                ><Loading/></div>}
                                <TimePeriodEventList contests={visibleEvents}
                                                     onClick={(contest) => this.handleContestOnMapClick(contest)}/>
                            </div>
                            <div className={"list-group list-group-root"}>
                                <div
                                    className={"d-flex justify-content-around list-group-item list-group-item-action list-group-item-secondary align-items-centre"}
                                    style={{paddingBottom: 0, paddingTop: 0}}>
                                    {!isIOS ? <a target={"_blank"}
                                                 href='https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1'><img
                                        alt='Get it on Google Play' style={{height: "45px"}}
                                        src='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png'/></a> : null}
                                    {!isAndroid ? <a target={"_blank"}
                                                     href="https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&amp;itscg=30200"><img
                                        style={{height: "45px", padding: "8px"}}
                                        src="https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us??size=500x166&amp;releaseDate=1436918400&h=a41916586b4763422c974414dc18bad0"
                                        alt="Download on the App Store"/></a> : null}
                                </div>

                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <EventSearchModal contests={this.props.contests} show={this.props.eventSearchModalShow}
                              handleContestClick={(contest) => this.handleContestClick(contest)}
                              dialogClassName="modal-xl" onHide={() => this.props.hideEventSearchModal()}/>
            <ContestPopupModal contest={popupContest} show={popupContest !== undefined}
                               participation={currentParticipation}
                               onHide={() => this.props.navigate("/")}/>
        </div>
    }
}

const GlobalEventList = connect(mapStateToProps, mapDispatchToProps)(ConnectedGlobalEventList);
export default withParams(GlobalEventList);