import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    displayExpandedHeader: state.displayExpandedHeader
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
                            <div className={"col-12 fill"}>
                    <a className={"btn"} data-toggle={"collapse"} data-target={"#insetMenu"} id={"menuButton"}>
                        <img id={'logoButton'}
                        alt={"Menu toggle"}
                        src={"/static/img/button.jpg"}/>
                    </a>

                                <div id="cesiumContainer"></div>
                                <div id className={"backdrop " + (this.props.displayExpandedHeader?"largeTable":"compactTable")}>{TrackerDisplay}</div>
                                {/*<div id="logoContainer"><img src={"/static/img/AirSportsLogo.png"} className={"img-fluid"}/>*/}
                                {/*</div>*/}
                            </div>
                        </div>
                    </div>
                </div>
            )
        }
    }
}

const TrackingContainer = connect(mapStateToProps)(ConnectedTrackingContainer)
export default TrackingContainer