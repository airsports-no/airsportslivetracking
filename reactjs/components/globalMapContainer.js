import 'regenerator-runtime/runtime'
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import GlobalMapMap from "./globalMapMap";
import {fetchContests} from "../actions";
import GlobalEventList from "./contests/globalEventList";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({})

class ConnectedGlobalMapContainer extends Component {
    constructor(props) {
        super(props);
    }

    componentDidMount() {
        this.props.fetchContests()
    }


    render() {
        let TrackerDisplay = <GlobalMapMap/>
        return (
            <div id="map-holder">
                <div id='main_div' className={"fill"}>
                    <div className={"fill"}>
                        <a className={"btn"} id="returnLink" href={"/"}>
                            <img src={"/static/img/hub.png"} id={"returnLinkImage"} alt={"Hub"}/>
                        </a>
                        <div className={"globalMapBackdrop"}>
                            <div
                                className={""}>
                                <div className={""}>
                                    <GlobalEventList/>
                                </div>
                            </div>

                        </div>
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
    GlobalMapContainer = connect(mapStateToProps, {fetchContests})(ConnectedGlobalMapContainer)
export default GlobalMapContainer