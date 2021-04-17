import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTasks/navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import {LowerThirdTeam} from "./teamBadges";
import {
    displayAllTracks,
    expandTrackingTable, fetchNavigationTask, fullHeightTable,
    halfHeightTable,
    hideLowerThirds,
    setDisplay,
    shrinkTrackingTable, toggleExplicitlyDisplayAllTracks
} from "../actions";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";
import Disclaimer from "./disclaimer";
import {mdiGoKartTrack, mdiMagnify, mdiPodium} from "@mdi/js";
import Icon from "@mdi/react";
import AboutTaskPopup from "./aboutTaskPopup";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    displayLowerThirds: state.displayLowerThirds,
    contestants: state.contestants,
    currentDisplay: state.currentDisplay,
    displayFullHeightTrackingTable: state.displayFullHeightTrackingTable
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
                                    {ExpandedTableLink}
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
                            <div className={"trackImage"}>
                                <Icon path={mdiGoKartTrack} title={"Logout"} size={2} color={"#e01b1c"} onClick={() => this.props.toggleExplicitlyDisplayAllTracks()}/>
                            </div>
                            <AboutTaskPopup navigationTask={this.props.navigationTask}/>
                            <div id="cesiumContainer"/>
                            {this.props.displayLowerThirds !== null ?
                                <LowerThirdTeam scorecard_data={this.props.navigationTask.scorecard_data}
                                                contestant={this.props.contestants[this.props.displayLowerThirds]}/> : null}

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
        toggleExplicitlyDisplayAllTracks
    })(ConnectedTrackingContainer)
export default TrackingContainer