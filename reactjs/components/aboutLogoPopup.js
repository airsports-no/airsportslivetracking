import React, {Component} from "react";
import {Button, Container, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {
    displayAboutModal,
    hideAboutModal,
} from "../actions";
import {mdiInformation, mdiLogin, mdiMagnify} from "@mdi/js";
import Icon from "@mdi/react";
import {SocialMediaLinks} from "./socialMediaLinks";
import {isAndroid, isIOS} from "react-device-detect";

const mapStateToProps = (state, props) => ({
    aboutModalShow: state.displayAboutModal,
})


function AboutLogoModal(props) {
    const {aboutText, ...other} = props
    return (
        <Modal {...other} aria-labelledby="contained-modal-title-vcenter" size={"lg"}>
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    <h2 className={"about-title"}>Welcome to Air Sports Live Tracking</h2>
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    Air Sports Live Tracking is an online tracking platform for general aviation leisure flying or
                    competitions. Use your cell phone as a tracker and share your position with other GA pilots. We fly
                    together!

                    Download the Air Sports Live Tracking app
                    from <a target={"_blank"}
                            href='https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1'>Google
                    Play</a> or <a target={"_blank"}
                                   href="https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&amp;itscg=30200">Apple
                    App Store</a>.
                    <div className={"d-flex justify-content-around"}>
                        {!isIOS ?
                            <div className={"p-2"}>
                                <a target={"_blank"}
                                   href='https://play.google.com/store/apps/details?id=no.airsports.android.livetracking&pcampaignid=pcampaignidMKT-Other-global-all-co-prtnr-py-PartBadge-Mar2515-1'><img
                                    alt='Get it on Google Play' style={{height: "60px"}}
                                    src='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png'/></a>
                            </div> : null}
                        {!isAndroid ?
                            <div className={"p-2"}>
                                <a target={"_blank"}
                                   href="https://apps.apple.com/us/app/air-sports-live-tracking/id1559193686?itsct=apps_box&amp;itscg=30200"><img
                                    style={{height: "60px", padding: "8px"}}
                                    src="https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us??size=500x166&amp;releaseDate=1436918400&h=a41916586b4763422c974414dc18bad0"
                                    alt="Download on the App Store"/></a>
                            </div> : null}
                    </div>
                    <hr style={{marginTop: 0}}/>
                        <div>
                            {aboutText}
                        </div>
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <img src={"/static/img/AirSportsLiveTracking.png"} alt={"Logo"} className={"mr-auto p-2 about-logo"}/>
                <SocialMediaLinks/>
            </Modal.Footer>

        </Modal>
);
}


class ConnectedAboutLogoPopup extends Component
    {
        constructor(props)
        {
            super(props)
        }

        render()
        {
            return <div>
                <a href={"#"} className={"logoImage"} onClick={this.props.displayAboutModal}>
                            <img src={"/static/img/airsports_info.png"} style={{width: "50px"}} alt={"About"}/>

                    {/*<Icon path={mdiInformation} title={"About"} size={this.props.size}*/}
                    {/*      color={this.props.colour ? this.props.colour : "#666666"}/>*/}
                    {/*<img className={"img-fluid"}*/}
                    {/*     src={"/static/img/about_live_tracking_shadow.png"}/>*/}
                </a>
                <AboutLogoModal aboutText={this.props.aboutText} show={this.props.aboutModalShow}
                                onHide={() => this.props.hideAboutModal()}/>
            </div>
        }
    }


const
AboutLogoPopup = connect(mapStateToProps,
    {
        displayAboutModal,
            hideAboutModal,
    }
)(ConnectedAboutLogoPopup)
export default AboutLogoPopup