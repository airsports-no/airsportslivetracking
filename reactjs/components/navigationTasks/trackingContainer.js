import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTask";
import { connect } from "react-redux";
import React, { Component } from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import { LowerThirdTeam } from "./teamBadges";
import {
    displayAllTracks,
    expandTrackingTable, fetchMyParticipatingContests, fetchNavigationTask,
    hideLowerThirds,
    setDisplay,
    shrinkTrackingTable, toggleDisplayOpenAip, toggleExplicitlyDisplayAllTracks
} from "../../actions";
import { SIMPLE_RANK_DISPLAY } from "../../constants/display-types";
import Disclaimer from "../disclaimer";
import { mdiAirplaneCog, mdiAirport, mdiGoKartTrack, mdiReplay, mdiTimerPlayOutline } from "@mdi/js";
import Icon from "@mdi/react";
import AboutTaskPopup from "./aboutTaskPopup";
import TimeDisplay from "./timeDisplay";
import qs from "qs";
import { withParams } from "../../utilities";


const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    navigationTaskError: state.navigationTaskError,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    displayLowerThirds: state.displayLowerThirds,
    contestants: state.contestants,
    currentDisplay: state.currentDisplay,
    myParticipatingContests: state.myParticipatingContests,
    webSocketOnline: state.webSocketOnline
})


class ConnectedTrackingContainer extends Component {
    constructor(props) {
        super(props);
        this.client = null;
        this.map = null;
        this.navigationTaskId = document.configuration.navigation_task_id;
        this.contestId = document.configuration.contest_id;
        this.displayMap = document.configuration.displayMap;
        this.displayTable = document.configuration.displayTable;
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.state = { height: window.innerHeight, width: window.innerWidth }
        this.contestantIds = []
        window.addEventListener("resize", () => this.setState({ height: window.innerHeight, width: window.innerWidth }))
    }

    fetchNavigationTask() {
        this.props.fetchNavigationTask(this.contestId, this.navigationTaskId, this.contestantIds);
    }

    componentDidMount() {
        const search = qs.parse(this.props.location.search, { ignoreQueryPrefix: true })
        if (search["contestantIds"] !== undefined) {
            this.contestantIds = search["contestantIds"].split(",").filter(x => x.trim().length && !isNaN(x)).map(Number)
        }

        this.fetchNavigationTask()
        this.props.fetchMyParticipatingContests()
    }

    resetToAllContestants() {
        this.props.setDisplay({ displayType: SIMPLE_RANK_DISPLAY })
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }

    getCurrentParticipation() {
        if (!this.props.myParticipatingContests) return null
        return this.props.myParticipatingContests.find((participation) => {
            return participation.contest.id === this.contestId
        })
    }

    render() {
        if (this.props.navigationTaskError) {
            return <div>
                <div className={"container-xl"}>
                    <h4 className="alert alert-warning" role="alert">Failed loading
                        contest: {this.props.navigationTaskError.statusText}</h4>
                    <p>Contact support or visit <a
                        href={'https://home.airsports.no/faq/#contest-results-are-not-found'}>our FAQ</a> for more
                        details.</p>
                </div>
            </div>
        }
        const ExpandedTableLink = <a className={"widthLink taskTitle"} href={"#"}
            onClick={this.props.displayExpandedTrackingTable ? this.props.shrinkTrackingTable : this.props.expandTrackingTable}>{this.props.displayExpandedTrackingTable ?
                <span className="iconify" data-icon="mdi-keyboard-arrow-left" /> :
                <span className="iconify" data-icon="mdi-keyboard-arrow-right" />
            }</a>
        // Expand this using scorecard information to select correct navigation task type that overrides map rendering
        const TrackerDisplay = <NavigationTask
            map={this.map}
            contestId={this.contestId}
            navigationTaskId={this.navigationTaskId}
            fetchInterval={2000}
            displayMap={this.displayMap}
            displayTable={true}
            contestantIds={this.contestantIds}
        />
        const currentParticipation = this.getCurrentParticipation()
        if (this.displayTable && this.displayMap) {
            return (
                <div id="map-holder">
                    <div id='main_div' className={"fill"}>
                        <div className={"row fill ml-1"}>
                            <div className={"col-5"}>
                                {TrackerDisplay}
                            </div>
                            <div className={"col-7 fill"}>
                                <div id="cesiumContainer" />
                            </div>
                        </div>
                    </div>
                </div>
            );
        } else if (this.displayTable) {
            return (
                <div id="map-holder">
                    <div id='main_div' className={"fill"}>
                        <div className={"row fill ml-1"}>
                            <div className={"col-12"}>
                                {TrackerDisplay}
                            </div>
                        </div>
                    </div>
                </div>
            );
        } else {
            return (
                <div id="map-holder">
                    <div id='main_div' className={"fill"}>
                        {this.props.navigationTask.contestant_set ? <TrackLoadingIndicator
                            numberOfContestants={Object.keys(this.props.contestants).length} /> : <div />}
                        {!this.props.webSocketOnline ? <div className={"offlineNotice"}>Off-Line, no data</div> : null}
                        <div className={"fill"}>
                            <div
                                className={"outerBackdrop " + (this.props.displayExpandedTrackingTable ? "outerBackdropWide" : "outerBackdropNarrow scalable") + " " + (this.props.displayExpandedTrackingTable ? "outerBackdropFull" : "outerBackdropHalf")}>
                                <div
                                    className={"titleWrapper"}>
                                    <a data-toggle={"collapse"} data-target={"#insetMenu"}
                                        style={{ paddingLeft: "14px", paddingRight: "12px" }}>
                                        <span className="iconify taskTitle" data-icon="mdi-menu" id={'menuButton'}></span>
                                    </a>
                                    <a href={"#"} className={'taskTitle taskTitleName'} data-toggle={"collapse"}
                                        aria-controls={"insetMenu"} aria-expanded={true}
                                        data-target={"#insetMenu"}>{this.props.navigationTask.name ? this.props.navigationTask.name.toUpperCase() : null}</a>
                                    {this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY ? ExpandedTableLink : null}
                                </div>
                                <div id={"insetMenu"}
                                    className={"collapse show"}>
                                    <div
                                        className={"backdrop " + (this.props.displayExpandedTrackingTable ? "backdropFull" : "backdropHalf")}>
                                        <div className={"text-light bg-dark"}>
                                            {TrackerDisplay}
                                        </div>
                                    </div>
                                </div>

                            </div>
                            <a className={"btn"} id="returnLink" href={"/"}>
                                <img src={document.configuration.STATIC_FILE_LOCATION + "img/AirSportsLiveTracking.png"} id={"returnLinkImage"} alt={"Home"} />
                            </a>
                            <Disclaimer />
                            {this.props.navigationTask.allow_self_management ?
                                <div className={"registerLink"}>
                                    {currentParticipation ?
                                        <a href={"/participation/myparticipation/" + currentParticipation.id + "/"}>
                                            <button className={"btn btn-danger btn-sm"}>Manage crew</button>
                                        </a> :
                                        <a href={"/participation/" + this.contestId + "/register/"}>
                                            <button className={"btn btn-danger btn-sm"}>Register crew</button>
                                        </a>}
                                </div> : null}
                            <div className={"trackImage"}>
                                <Icon path={mdiGoKartTrack} title={"Display airplane tracks"} size={2} color={"#e01b1c"}
                                    onClick={() => this.props.toggleExplicitlyDisplayAllTracks()} />
                            </div>
                            {this.props.navigationTask.display_background_map ?
                                <div className={"openAipLink"}>
                                    <Icon path={mdiAirport} title={"Show OpenAIP overlay"} size={2} color={"#e01b1c"}
                                        onClick={() => this.props.toggleDisplayOpenAip()} />
                                </div> : null}
                            <AboutTaskPopup navigationTask={this.props.navigationTask} />
                            {/* <div className={"replayIcon"}>
                                {!this.playback ?
                                    <a href={document.configuration.playbackLink+(this.contestantIds.length > 0? "?contestantIds=" + this.contestantIds.join(",") : "")}><Icon
                                        path={mdiReplay} title={"Replay the navigation task after-the-fact"} size={2}
                                        color={"#e01b1c"}/></a> :
                                    <a href={document.configuration.liveMapLink+(this.contestantIds.length > 0 ? "?contestantIds=" + this.contestantIds.join(",") : "")}><Icon
                                        path={mdiTimerPlayOutline} title={"Switch to live view"} size={2}
                                        color={"#e01b1c"}/></a>
                                }
                            </div> */}
                            {document.configuration.canChangeNavigationTask ? <div className={"managementIcon"}>
                                <a href={document.configuration.navigationTaskManagementLink}><Icon
                                    path={mdiAirplaneCog} title={"Manage task"} size={2} color={"#e01b1c"} /></a>
                            </div> : null}
                            <div id="cesiumContainer" />
                            <TimeDisplay class={"pilotTime"} />
                            {this.props.displayLowerThirds !== null && this.props.contestants[this.props.displayLowerThirds] ?
                                <LowerThirdTeam scorecard={this.props.navigationTask.scorecard}
                                    contestant={this.props.contestants[this.props.displayLowerThirds]}
                                    contestantId={this.props.displayLowerThirds} />
                                : null}

                        </div>
                    </div>
                </div>
            )
        }
    }
}

const
    TrackingContainer = connect(mapStateToProps, {
        fetchNavigationTask,
        expandTrackingTable,
        shrinkTrackingTable,
        setDisplay,
        displayAllTracks,
        hideLowerThirds,
        toggleExplicitlyDisplayAllTracks,
        toggleDisplayOpenAip,
        fetchMyParticipatingContests
    })(ConnectedTrackingContainer)
export default withParams(TrackingContainer)