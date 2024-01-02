import React, {Component} from "react";
import { Container, Form, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {
    displayAboutModal,
    hideAboutModal, toggleBackgroundMap, toggleProfilePictures, toggleSecretGates,
} from "../../actions";
import {SocialMediaLinks} from "../socialMediaLinks";
import {isAndroid, isIOS} from "react-device-detect";
import Cookies from 'universal-cookie';

const _ = require('lodash');

const mapStateToPropsModal = (state, props) => ({
    navigationTask: state.navigationTask,
    displaySecretGates: state.displaySecretGates,
    displayBackgroundMap: state.displayBackgroundMap,
    displayProfilePictures: state.displayProfilePictures
})

const mapStateToProps = (state, props) => ({
    aboutModalShow: state.displayAboutModal,
})


class ConnectedAboutLogoModal extends Component {
    constructor(props) {
        super(props)
        this.loadSettings()
    }

    loadSettings() {
        const cookies = new Cookies();
        this.settings = _.get(cookies.get("aslt_settings") || {}, [this.props.navigationTask.id], {})
        this.props.toggleSecretGates(_.get(this.settings, ["displaySecretGates"], true))
        this.props.toggleBackgroundMap(_.get(this.settings, ["displayBackgroundMap"], true))
        this.props.toggleProfilePictures(_.get(this.settings, ["displayProfilePictures"], true))
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
        if (this.props.navigationTask !== prevProps.navigationTask) {
            this.loadSettings()
        }
    }

    saveSettings() {
        console.log("Saving settings")
        console.log(this.settings)
        const cookies = new Cookies();
        const settings = cookies.get("aslt_settings") || {}
        settings[this.props.navigationTask.id] = this.settings
        cookies.set("aslt_settings", settings)
    }

    toggleSecretGates(visible) {
        this.settings.displaySecretGates = visible
        this.saveSettings()
        this.props.toggleSecretGates(visible)
    }

    toggleBackgroundMap(visible) {
        this.settings.displayBackgroundMap = visible
        this.saveSettings()
        this.props.toggleBackgroundMap(visible)
    }

    toggleProfilePictures(visible) {
        this.settings.displayProfilePictures = visible
        this.saveSettings()
        this.props.toggleProfilePictures(visible)
    }

    render() {
        const {aboutText, ...other} = this.props
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
                        competitions. Use your cell phone as a tracker and share your position with other GA pilots. We
                        fly
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
                        <hr style={{marginTop: 0}}/>
                        <div>
                            <h3>Settings</h3>
                            <Form.Group>
                                {this.props.displaySecretGatesToggle ? <Form.Check type={"checkbox"} onChange={(e) => {
                                    this.toggleSecretGates(e.target.checked)
                                }} checked={this.props.displaySecretGates} label={"Display secret gates"}
                                                                                   disabled={!this.props.navigationTask.display_secrets}/> : null}
                                <Form.Check type={"checkbox"} onChange={(e) => {
                                    this.toggleBackgroundMap(e.target.checked)
                                }} checked={this.props.displayBackgroundMap} label={"Display background map"}
                                            disabled={!this.props.navigationTask.display_background_map}/>

                                <Form.Check type={"checkbox"} onChange={(e) => {
                                    this.toggleProfilePictures(e.target.checked)
                                }} checked={this.props.displayProfilePictures} label={"Display profile pictures"}/>
                            </Form.Group>
                            <b>
                                {this.props.navigationTask.calculation_delay_minutes === 0 ? "Data is live" : "Data is delayed by " + this.props.navigationTask.calculation_delay_minutes + " minutes"}
                            </b>
                        </div>
                    </Container>
                </Modal.Body>
                <Modal.Footer>
                    <img src={"/static/img/AirSportsLiveTracking.png"} alt={"Logo"}
                         className={"mr-auto p-2 about-logo"}/>
                    <SocialMediaLinks/>
                </Modal.Footer>

            </Modal>
        );
    }
}

const AboutLogoModal = connect(mapStateToPropsModal, {
    toggleSecretGates,
    toggleBackgroundMap,
    toggleProfilePictures
})(ConnectedAboutLogoModal)

class ConnectedAboutLogoPopup extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <div>
            <a href={"#"} className={"logoImage"} onClick={this.props.displayAboutModal}>
                <img src={"/static/img/airsports_info.png"} style={{width: "50px"}} alt={"About"}/>
            </a>
            <AboutLogoModal aboutText={this.props.aboutText} show={this.props.aboutModalShow}
                            onHide={() => this.props.hideAboutModal()}
                            displaySecretGatesToggle={this.props.displaySecretGatesToggle}/>
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