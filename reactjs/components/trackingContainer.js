import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import {LowerThirdTeam} from "./teamBadges";
import {
    displayAllTracks,
    expandTrackingTable, fullHeightTable,
    halfHeightTable,
    hideLowerThirds,
    setDisplay,
    shrinkTrackingTable
} from "../actions";
import {SIMPLE_RANK_DISPLAY} from "../constants/display-types";

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
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
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
        const TrackerDisplay =
            <NavigationTask map={this.map} contestId={this.contestId} navigationTaskId={this.navigationTaskId}
                            fetchInterval={2000}
                            displayMap={this.displayMap} displayTable={true}/>
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
                                className={"outerBackdrop " + (this.props.displayExpandedTrackingTable ? "outerBackdropWide" : "outerBackdropNarrow") + " " + (this.props.displayExpandedTrackingTable ? "outerBackdropFull" : "outerBackdropHalf")}>
                                <div
                                    className={"titleWrapper"}>
                                    <a data-toggle={"collapse"} data-target={"#insetMenu"} style={{paddingLeft: "14px", paddingRight: "12px"}}>
                                        {/*id={"logoButtonWrapper"}>*/}
                                        <i className={"taskTitle mdi mdi-menu"} id={'menuButton'}/>
                                    </a>
                                    <a href={"#"} className={'taskTitle taskTitleName'} data-toggle={"collapse"}
                                       data-target={"#insetMenu"}>{this.props.navigationTask.name?this.props.navigationTask.name.toUpperCase():null}</a>
                                    {ExpandedTableLink}
                                    {/*{TableHeightLink}*/}
                                </div>
                                <div id={"insetMenu"}
                                     aria-expanded={false} aria-controls={"insetMenu"} className={"collapse"}>
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
                                {/*<i className={"mdi mdi-home"} id={"returnLinkImage"}/>*/}
                                <img src={"/static/img/hub.png"} id={"returnLinkImage"} alt={"Hub"}/>
                            </a>
                            <div id={"disclaimer"}>
                                <img src={"/static/img/nlf_white.png"} className={"logo"}/>
                                THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING IN COLLABORATION<br/>
                                WITH NORGES LUFTSPORTSFORBUND NLF - <a href={"#"} style={{color: "white"}}>FOR MORE INFO / DISCLAIMER</a>
                            </div>

                            {/*<div id={"sponsor"}>*/}
                            {/*    <img src={"/static/img/IG.png"} className={"logo img-fluid"}/>*/}
                            {/*</div>*/}
                            <div className={"logoImage"}>
                                <img className={"img-fluid"} src={"/static/img/live_tracking.png"} />
                            </div>
                            {/*<img alt={"Logo"} className={"logoImage"}*/}
                            {/*     id={"logoImage"}*/}
                            {/*     src={"/static/img/airsports.png"}/>*/}
                            <div id="cesiumContainer"/>
                            {this.props.displayLowerThirds !== null ?
                                <LowerThirdTeam
                                    contestant={this.props.contestants[this.props.displayLowerThirds]}/> : null}

                            {/*<div id="logoContainer"><img src={"/static/img/AirSportsLogo.png"} className={"img-fluid"}/>*/}
                            {/*</div>*/}
                        </div>
                    </div>
                </div>
            )
        }
    }
}

const TrackingContainer = connect(mapStateToProps, {
    expandTrackingTable,
    shrinkTrackingTable,
    setDisplay,
    displayAllTracks,
    hideLowerThirds,
    halfHeightTable,
    fullHeightTable
})(ConnectedTrackingContainer)
export default TrackingContainer