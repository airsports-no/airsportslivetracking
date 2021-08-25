import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTasks/navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import {LowerThirdTeam} from "./teamBadges";
import {
    displayAllTracks,
    expandTrackingTable, fetchMyParticipatingContests, fetchNavigationTask, fullHeightTable,
    halfHeightTable,
    hideLowerThirds,
    setDisplay,
    shrinkTrackingTable, toggleDisplayOpenAip, toggleExplicitlyDisplayAllTracks
} from "../actions";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import Disclaimer from "./disclaimer";
import {mdiAirport, mdiGoKartTrack, mdiMagnify, mdiPodium} from "@mdi/js";
import Icon from "@mdi/react";
import AboutTaskPopup from "./aboutTaskPopup";
import TimeDisplay from "./timeDisplay";
import {Link} from "react-router-dom";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    displayLowerThirds: state.displayLowerThirds,
    contestants: state.contestants,
    currentDisplay: state.currentDisplay,
    displayFullHeightTrackingTable: state.displayFullHeightTrackingTable,
    myParticipatingContests: state.myParticipatingContests
})

class ConnectedTrackingContainer extends Component {
    constructor(props) {
        super(props);
        this.client = null;
        this.viewer = null;
        this.map = null;
        this.navigationTaskId = document.configuration.navigation_task_id;
        this.contestId = document.configuration.contest_id;
        this.displayMap = document.configuration.displayMap;
        this.displayTable = document.configuration.displayTable;
        this.playback = document.configuration.playback;
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
    }

    fetchNavigationTask() {
        this.props.fetchNavigationTask(this.contestId, this.navigationTaskId);
        setTimeout(() => this.fetchNavigationTask(), 300000)
    }

    componentDidMount() {
        this.fetchNavigationTask()
    }

    resetToAllContestants() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
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
        const TableHeightLink = <a className={"heightLink taskTitle"} href={"#"}
                                   onClick={this.props.displayFullHeightTrackingTable ? this.props.halfHeightTable : this.props.fullHeightTable}>{this.props.displayFullHeightTrackingTable ?
            <i className={"mdi mdi-keyboard-arrow-up"}/> :
            <i className={"mdi mdi-keyboard-arrow-down"}/>}</a>
        const ExpandedTableLink = <a className={"widthLink taskTitle"} href={"#"}
                                     onClick={this.props.displayExpandedTrackingTable ? this.props.shrinkTrackingTable : this.props.expandTrackingTable}>{this.props.displayExpandedTrackingTable ?
            <i className={"mdi mdi-keyboard-arrow-left"}/> :
            <i className={"mdi mdi-keyboard-arrow-right"}/>}</a>
        // Expand this using scorecard information to select correct navigation task type that overrides map rendering
        let TrackerDisplay = <NavigationTask map={this.map} contestId={this.contestId}
                                             navigationTaskId={this.navigationTaskId}
                                             fetchInterval={2000}
                                             displayMap={this.displayMap} displayTable={true} playback={this.playback}/>
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
                                <div id="cesiumContainer"/>
                                {/*<div id="logoContainer"><img src={"/static/img/AirSportsLogo.png"} className={"img-fluid"}/>*/}
                                {/*</div>*/}
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
                            numberOfContestants={this.props.navigationTask.contestant_set.length}/> : <div/>}
                        <div className={"fill"}>
                            <div
                                className={"outerBackdrop " + (this.props.displayExpandedTrackingTable ? "outerBackdropWide" : "outerBackdropNarrow scalable") + " " + (this.props.displayExpandedTrackingTable ? "outerBackdropFull" : "outerBackdropHalf")}>
                                <div
                                    className={"titleWrapper"}>
                                    <a data-toggle={"collapse"} data-target={"#insetMenu"}
                                       style={{paddingLeft: "14px", paddingRight: "12px"}}>
                                        {/*id={"logoButtonWrapper"}>*/}
                                        <i className={"taskTitle mdi mdi-menu"} id={'menuButton'}/>
                                    </a>
                                    <a href={"#"} className={'taskTitle taskTitleName'} data-toggle={"collapse"}
                                       data-target={"#insetMenu"}>{this.props.navigationTask.name ? this.props.navigationTask.name.toUpperCase() : null}</a>
                                    {this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY ? ExpandedTableLink : null}
                                    {/*{TableHeightLink}*/}
                                </div>
                                <div id={"insetMenu"}
                                     aria-expanded={true} aria-controls={"insetMenu"} className={"collapse show"}>
                                    <div
                                        className={"backdrop " + (this.props.displayExpandedTrackingTable ? "backdropFull" : "backdropHalf")}>
                                        <div className={"text-light bg-dark"}>
                                            {TrackerDisplay}
                                        </div>
                                    </div>
                                    {/*<div className={"bottomWrapper"}>{TableHeightLink} {ExpandedTableLink}</div>*/}
                                </div>

                            </div>
                            <a className={"btn"} id="returnLink" href={"/"}>
                                <img src={"/static/img/AirSportsLiveTracking.png"} id={"returnLinkImage"} alt={"Home"}/>
                            </a>
                            <Disclaimer/>
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
                                <Icon path={mdiGoKartTrack} title={"Track"} size={2} color={"#e01b1c"}
                                      onClick={() => this.props.toggleExplicitlyDisplayAllTracks()}/>
                            </div>
                            <div className={"openAipLink"}>
                                <Icon path={mdiAirport} title={"OpenAIP"} size={2} color={"#e01b1c"}
                                      onClick={() => this.props.toggleDisplayOpenAip()}/>
                            </div>
                            <AboutTaskPopup navigationTask={this.props.navigationTask}/>
                            <div id="cesiumContainer"/>
                            {this.props.displayLowerThirds !== null ?
                                <div><LowerThirdTeam scorecard_data={this.props.navigationTask.scorecard_data}
                                                     contestant={this.props.contestants[this.props.displayLowerThirds]}/>
                                    {/*<TimeDisplay contestantId={this.props.displayLowerThirds} class={"pilotTime"}/>*/}
                                    <TimeDisplay class={"pilotTime"}/>
                                </div> : <TimeDisplay class={"pilotTime"}/>}

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
        halfHeightTable,
        fullHeightTable,
        toggleExplicitlyDisplayAllTracks,
        toggleDisplayOpenAip,
        fetchMyParticipatingContests
    })(ConnectedTrackingContainer)
export default TrackingContainer