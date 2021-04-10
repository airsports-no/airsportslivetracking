import React, {Component} from "react";
import {connect} from "react-redux";
// Firebase App (the core Firebase SDK) is always required and must be listed first
import firebase from "firebase/app";
// If you are using v7 or any earlier version of the JS SDK, you should import firebase using namespace import
// import * as firebase from "firebase/app"

// If you enabled Analytics in your project, add the Firebase SDK for Analytics
import "firebase/analytics";

// Add the Firebase products that you want to use
import "firebase/auth";
import {Button, Container, Form, Modal} from "react-bootstrap";

const firebaseConfig = {
    apiKey: "AIzaSyCcOlh07D2-7p0W2coNK_sZ2g8-JxxbPSE",
    authDomain: "airsports-613ce.firebaseapp.com",
    projectId: "airsports-613ce",
    storageBucket: "airsports-613ce.appspot.com",
    messagingSenderId: "583405520610",
    appId: "1:583405520610:web:6c07169205b277b96cc0bb",
    measurementId: "G-V9SQR3ZYRB"
};

class ConnectedEmailLinkValidator extends Component {
    constructor(props) {
        super(props)
        this.state = {
            displayInformationModal: false,
            informationModalTitle: "",
            informationModalText: "",
            displayMailModal: false,
            mail: ""
        }
        firebase.initializeApp(firebaseConfig);
    }

    verificationModal() {
        return (
            <Modal show={this.state.displayMailModal} onHide={() => this.setState({displayMailModal: false})}
                   aria-labelledby="contained-modal-title-vcenter">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        Input email for validation
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Container>
                        <Form.Group>
                            <Form.Label>Email address</Form.Label>
                            <Form.Control type={"text"} onChange={(e) => {
                                this.setState({
                                    mail: e.target.value
                                })
                            }} value={this.state.mail}/>
                        </Form.Group>
                    </Container>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={() => this.performValidation()}>Validate</Button>
                </Modal.Footer>
            </Modal>
        );
    }

    informationModal() {
        return (
            <Modal show={this.state.displayInformationModal}
                   onHide={() => {
                       window.location = "/"
                   }}
                   aria-labelledby="contained-modal-title-vcenter">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        {this.state.informationModalTitle}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Container>
                        {this.state.informationModalText}
                    </Container>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={() => {
                        window.location = "/"
                    }}>OK</Button>
                </Modal.Footer>
            </Modal>
        );
    }

    performValidation() {
        this.setState({displayMailModal: false})
        firebase.auth().signInWithEmailLink(this.state.mail, window.location.href)
            .then((result) => {
                // Clear email from storage.
                window.localStorage.removeItem('emailForSignIn');
                // You can access the new user via result.user
                // Additional user info profile not available via:
                // result.additionalUserInfo.profile == null
                // You can check if the user is new or existing:
                // result.additionalUserInfo.isNewUser
                this.setState({
                    displayInformationModal: true,
                    informationModalTitle: "Success",
                    informationModalText: "Email successfully verified. Please restart the app to be logged in."
                })
            })
            .catch((error) => {
                this.setState({
                    displayInformationModal: true,
                    informationModalTitle: "Failure",
                    informationModalText: error.message
                })
                console.log(error)
                // Some error occurred, you can inspect the code: error.code
                // Common errors could be invalid email and invalid or expired OTPs.
            });

    }

    componentDidMount() {
        if (firebase.auth().isSignInWithEmailLink(window.location.href)) {
            this.setState({displayMailModal: true})
        }
    }


    render(){
        return <div>{this.verificationModal()}{this.informationModal()}</div>
    }
}

export const mapStateToProps = (state, props) => ({})
export const mapDispatchToProps = {}


const
    EmailLinkValidator = connect(mapStateToProps, mapDispatchToProps)(ConnectedEmailLinkValidator);
export default EmailLinkValidator;