import React, {Component} from "react";
import {Button, Container, Form, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {
    displayAboutModal, displayWikiModal,
    hideAboutModal, hideWikiModal, toggleBackgroundMap, toggleProfilePictures, toggleSecretGates,
} from "../actions";
import {mdiInformation, mdiLogin, mdiMagnify} from "@mdi/js";
import Icon from "@mdi/react";
import {SocialMediaLinks} from "./socialMediaLinks";
import {isAndroid, isIOS} from "react-device-detect";
import Cookies from 'universal-cookie';
import axios from "../../src/static/jquery-ui/external/jquery/jquery";

const _ = require('lodash');

const mapStateToPropsModal = (state, props) => ({})

const mapStateToProps = (state, props) => ({
    wikiModalShow: state.displayWikiModal,
})


class ConnectedWikiLogoModal extends Component {
    constructor(props) {
        super(props)
        this.state = {
            content: null
        }
        this.fetchContent()
    }

    fetchContent() {
        axios.get('/cmsapi/v2/pages/?type=wiki.BodyPage&slug=airsportsnews&fields=*').then((res) => {
            console.log(res)
            this.setState({
                title: res.items.length > 0 ? res.items[0].title : "",
                content: res.items.length > 0 ? res.items[0].body : ""
            })
        })
    }

    render() {
        const {aboutText, ...other} = this.props
        return (
            <Modal {...other} aria-labelledby="contained-modal-title-vcenter" size={"lg"}>
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        <h2 className={"about-title"}>{this.state.title}</h2>
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Container>
                        <div dangerouslySetInnerHTML={{__html: this.state.content}}/>
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

const WikiLogoModal = connect(mapStateToPropsModal, {})(ConnectedWikiLogoModal)

class ConnectedWikiLogoPopup extends Component {
    constructor(props) {
        super(props)
    }

    render() {
        return <div>
            <a href={"https://home.airsports.no/"} className={"wikiImage"}>
                <img src={"/static/img/news.png"} style={{width: "50px"}} alt={"About"}/>
            </a>
        </div>
    }
}


const
    WikiLogoPopup = connect(mapStateToProps,
        {
            displayWikiModal,
            hideWikiModal,
        }
    )(ConnectedWikiLogoPopup)
export default WikiLogoPopup