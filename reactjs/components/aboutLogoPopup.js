import React, {Component} from "react";
import {Container, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {
    displayAboutModal,
    hideAboutModal,
} from "../actions";
import {mdiMagnify} from "@mdi/js";
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
                    About Air Sports Live Tracking
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    <div>
                        Air Sports Live Tracking is an online tracking platform for use in competition flying and social flying events.
                    </div>
                    <div>
                        {aboutText}
                    </div>
                    {/*<div dangerouslySetInnerHTML={{__html: aboutText}}/>*/}
                    <SocialMediaLinks/>
                </Container>
            </Modal.Body>
        </Modal>
    );
}


class ConnectedAboutLogoPopup extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <div>
            <div className={"logoImage"} onClick={this.props.displayAboutModal}>
                <img className={"img-fluid"}
                     src={"/static/img/about_live_tracking_shadow.png"}/>
            </div>
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