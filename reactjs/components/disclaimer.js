import React, {Component} from "react";
import {Button, Container, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {displayDisclaimerModal, fetchContests, fetchDisclaimer, hideDisclaimerModal} from "../actions";

const mapStateToProps = (state, props) => ({
    disclaimerModalShow: state.displayDisclaimerModal,
    disclaimer: state.disclaimer
})


function DisclaimerLong(props) {
    return (
        <Modal {...props} aria-labelledby="contained-modal-title-vcenter">
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Disclaimer
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    <div dangerouslySetInnerHTML={{__html: props.disclaimer}}/>
                </Container>
            </Modal.Body>
            {/*<Modal.Footer>*/}
            {/*    <Button onClick={props.onHide}>Close</Button>*/}
            {/*</Modal.Footer>*/}
        </Modal>
    );
}


class ConnectedDisclaimer extends Component {
    constructor(props) {
        super(props)
    }

    componentDidMount() {
        this.props.fetchDisclaimer()
    }

    render() {
        return <div>
            <div id={"disclaimer"} onClick={this.props.displayDisclaimerModal}>
                <img src={"/static/img/airsports_no_text_white.png"} className={"logo"}/>
                THIS SERVICE IS PROVIDED BY AIR SPORTS LIVE TRACKING, AND IS INTENDED FOR ENTERTAINMENT ONLY!
                PLEASE CLICK FOR THE FULL DISCLAIMER.
            </div>
            <DisclaimerLong disclaimer={this.props.disclaimer} show={this.props.disclaimerModalShow}
                            dialogClassName="modal-90w" onHide={() => this.props.hideDisclaimerModal()}/>
        </div>
    }
}


const
    Disclaimer = connect(mapStateToProps, {
        displayDisclaimerModal,
        hideDisclaimerModal,
        fetchDisclaimer
    })(ConnectedDisclaimer)
export default Disclaimer