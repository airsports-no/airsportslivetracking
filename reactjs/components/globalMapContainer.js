import 'regenerator-runtime/runtime'
import {connect} from "react-redux";
import React, {Component} from "react";
import GlobalMapMap from "./globalMapMap";
import {displayDisclaimerModal, fetchContests, hideDisclaimerModal} from "../actions";
import GlobalEventList from "./contests/globalEventList";
import Disclaimer, {DisclaimerLong} from "./disclaimer";
import AboutLogoPopup from "./aboutLogoPopup";
import aboutGlobalMap from "./aboutTexts/aboutGlobalMap";
import {internalColour, ognColour, safeskyColour} from "./aircraft/aircraft";
import {withRouter} from "react-router-dom";
import OngoingNavigationTicker from "./contests/ongoingNavigationTicker";
import WikiLogoPopup from "./wikiPopup";

const mapStateToProps = (state, props) => ({})

class ConnectedGlobalMapContainer extends Component {
    constructor(props) {
        super(props);
    }

    componentDidMount() {
        this.props.fetchContests()
    }


    render() {
        return (
            <div id="map-holder">
                <div id='main_div' className={"fill"}>
                    <div className={"fill"}>
                        <a className={"btn"} id="returnLink" href={"/"}>
                            <img src={"/static/img/AirSportsLiveTracking.png"} id={"returnLinkImage"} alt={"Home"}/>
                        </a>
                        <GlobalEventList contestDetailsId={this.props.contestDetailsId}/>
                        <div className={"aircraft-legend-global"}>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: internalColour}}/> AirSports<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: safeskyColour}}/> Safesky<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "#C70039", opacity: 0.4}}/> &lt;40kts<br/>
                            <i className="mdi mdi-airplanemode-active"
                               style={{color: "grey", opacity: 0.4}}/> &gt;20sec
                        </div>
                        <Disclaimer/>
                        <AboutLogoPopup aboutText={aboutGlobalMap} size={2}/>
                        <WikiLogoPopup size={2}/>
                        <div id="cesiumContainer"/>
                        <div className="ongoing-navigation-ticker"><OngoingNavigationTicker/></div>
                    </div>
                </div>
                <GlobalMapMap/>
            </div>
        )
    }
}

const
    GlobalMapContainer = connect(mapStateToProps, {
        fetchContests,
    })(withRouter(ConnectedGlobalMapContainer))
export default GlobalMapContainer