import 'regenerator-runtime/runtime'
import NavigationTask from "./navigationTask";
import {connect} from "react-redux";
import React, {Component} from "react";

// import "leaflet/dist/leaflet.css"

class ConnectedTrackingContainer extends Component {
    constructor(props) {
        super(props);
        this.client = null;
        this.viewer = null;
        this.map = null;
        this.navigationTaskId = document.configuration.navigation_task_id;
        this.displayMap = document.configuration.displayMap;
        this.displayTable = document.configuration.displayTable;
    }


    render() {
        const TrackerDisplay =
            <NavigationTask map={this.map} navigationTaskId={this.navigationTaskId} fetchInterval={5000}
                            displayMap={this.displayMap} displayTable={this.displayTable}/>
        if (this.displayTable && this.displayMap) {
            return (
                <div id="map-holder">
                    <div id='main_div' className={"container-fluid fill"}>
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
                    <div id='main_div' className={"container-fluid fill"}>
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
                    <div id='main_div' className={"container-fluid fill"}>
                        <div className={"row fill ml-1"}>
                            {TrackerDisplay}
                            <div className={"col-12 fill"}>
                                <div id="cesiumContainer"></div>
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

const TrackingContainer = connect()(ConnectedTrackingContainer)
export default TrackingContainer