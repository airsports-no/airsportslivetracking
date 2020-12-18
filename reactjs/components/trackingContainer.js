import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable
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
    }


    render() {
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
                        <div className={"row fill ml-1"}>
                            <a className={"btn"} data-toggle={"collapse"} data-target={"#insetMenu"}
                               id={"logoButtonWrapper"}>
                                <img id={'logoButton'}
                                     alt={"Menu toggle"}
                                     src={"/static/img/airsports.png"}/>
                            </a>
                            <a className={"btn"} id="returnLink" href={"/"}><img alt={"Back to main page"}
                                                                                 id={"returnLinkImage"}
                                                                                 src={"/static/img/AirSportsLogo.png"}/></a>
                            <div id="cesiumContainer"/>
                            <div
                                className={"backdrop " + (this.props.displayExpandedTrackingTable ? "largeTable" : "compactTable")}>{TrackerDisplay}</div>
                            {/*<div id="logoContainer"><img src={"/static/img/AirSportsLogo.png"} className={"img-fluid"}/>*/}
                            {/*</div>*/}
                        </div>
                    </div>
                </div>
            )
        }
    }
}

const TrackingContainer = connect(mapStateToProps)(ConnectedTrackingContainer)
export default TrackingContainer