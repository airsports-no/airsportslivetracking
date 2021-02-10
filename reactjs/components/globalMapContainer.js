import 'regenerator-runtime/runtime'
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import GlobalMapMap from "./globalMapMap";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({})

class ConnectedGlobalMapContainer extends Component {
    constructor(props) {
        super(props);
    }

    render() {
        let TrackerDisplay = <GlobalMapMap/>
        return (
            <div id="map-holder">
                <div id='main_div' className={"fill"}>
                    <div className={"fill"}>
                        <a className={"btn"} id="returnLink" href={"/contest/"}>
                            <img src={"/static/img/hub.png"} id={"returnLinkImage"} alt={"Hub"}/>
                        </a>
                        <div id={"disclaimer"}>
                            <img src={"/static/img/nlf_white.png"} className={"logo"}/>
                            THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING IN COLLABORATION<br/>
                            WITH NORGES LUFTSPORTSFORBUND NLF - <a href={"#"} style={{color: "white"}}>FOR MORE
                            INFO / DISCLAIMER</a>
                        </div>

                        <div className={"logoImage"}>
                            <img className={"img-fluid"}
                                 src={"/static/img/live_tracking.png"}/>
                        </div>
                        <div id="cesiumContainer"/>
                    </div>
                </div>
                {TrackerDisplay}
            </div>
        )
    }
}

const
    GlobalMapContainer = connect(mapStateToProps, {})(ConnectedGlobalMapContainer)
export default GlobalMapContainer