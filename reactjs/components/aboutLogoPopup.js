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

const mapStateToProps = (state, props) => ({
    aboutModalShow: state.displayAboutModal,
})


function AboutLogoModal(props) {
    const {aboutText, ...other} = props
    return (
        <Modal {...other} aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    <b>About Air Sports Live Tracking</b>
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    <div>
                        Air Sports Live Tracking is an online tracking platform for use in competition flying and social
                        flying events.
                    </div>
                    <hr/>
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


class ConnectedAboutLogoPopup extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <div>
            <a href={"#"} className={"logoImage"} onClick={this.props.displayAboutModal}>
                <Icon path={mdiInformation} title={"About"} size={this.props.size} color={this.props.colour?this.props.colour:"#666666"}/>
                {/*<img className={"img-fluid"}*/}
                {/*     src={"/static/img/about_live_tracking_shadow.png"}/>*/}
            </a>
            <AboutLogoModal aboutText={this.props.aboutText} show={this.props.aboutModalShow}
                            dialogClassName="modal-60w" onHide={() => this.props.hideAboutModal()}/>
        </div>
    }
}


const
    AboutLogoPopup = connect(mapStateToProps, {
        displayAboutModal,
        hideAboutModal,
    })(ConnectedAboutLogoPopup)
export default AboutLogoPopup