import 'regenerator-runtime/runtime'
import {connect} from "react-redux";
import React, {Component} from "react";
import TrackLoadingIndicator from "./trackLoadingIndicator";
import GlobalMapMap from "./globalMapMap";
import {displayDisclaimerModal, fetchContests, hideDisclaimerModal} from "../actions";
import GlobalEventList from "./contests/globalEventList";
import Disclaimer, {DisclaimerLong} from "./disclaimer";
import {SocialMediaLinks} from "./socialMediaLinks";
import AboutLogoPopup from "./aboutLogoPopup";
import aboutGlobalMap from "./aboutTexts/aboutGlobalMap";

// import "leaflet/dist/leaflet.css"

const mapStateToProps = (state, props) => ({
})

class ConnectedGlobalMapContainer extends Component {
    constructor(props) {
        super(props);
    }

    componentDidMount() {
        this.props.fetchContests()
    }


    render() {
        let settingsButton = null
        if (document.configuration.managementLink) {
            settingsButton = <a className={"btn"} id="settingsLink" href={document.configuration.managementLink}>
                <i className={"taskTitle mdi mdi-settings"} id={'menuButton'}/>
            </a>
        }

        let TrackerDisplay = <GlobalMapMap/>
        return (
            <div id="map-holder">
                <div id='main_div' className={"fill"}>
                    <div className={"fill"}>
                        <a className={"btn"} id="returnLink" href={"/"}>
                            <img src={"/static/img/hub.png"} id={"returnLinkImage"} alt={"Hub"}/>
                        </a>
                        <GlobalEventList/>
                        <Disclaimer/>

                        {/*<SocialMediaLinks/>*/}
                        {/*{settingsButton}*/}
                        <AboutLogoPopup aboutText={aboutGlobalMap}/>
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