import 'regenerator-runtime/runtime'
import {connect} from "react-redux";
import React, {Component} from "react";
import GlobalMapMap from "./globalMapMap";
import {displayDisclaimerModal, fetchContests, hideDisclaimerModal} from "../actions";
import GlobalEventList from "./contests/globalEventList";
import Disclaimer, {DisclaimerLong} from "./disclaimer";
import AboutLogoPopup from "./aboutLogoPopup";
import aboutGlobalMap from "./aboutTexts/aboutGlobalMap";

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
                            <img src={"/static/img/AirSportsLiveTracking.png"} id={"returnLinkImage"} alt={"Home"}/>
                        </a>
                        <GlobalEventList/>
                        <div className={"aircraft-legend-global"}>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "#2471a3"}}/> AirSports<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "#7d3c98"}}/> OpenSky<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "#2471a3", opacity: 0.4}}/> &lt;40kts<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "grey", opacity: 0.4}}/> &gt;20sec
                        </div>
                        <Disclaimer/>
                        <AboutLogoPopup aboutText={aboutGlobalMap} size={2}/>
                        <div id="cesiumContainer"/>
                    </div>
                </div>
                {TrackerDisplay}
            </div>
        )
    }
}

const
    GlobalMapContainer = connect(mapStateToProps, {
        fetchContests,
    })(ConnectedGlobalMapContainer)
export default GlobalMapContainer