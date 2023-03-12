import React, {Component} from "react";
import {Button, Container, Modal} from "react-bootstrap";
import {connect} from "react-redux";
import {displayDisclaimerModal, fetchDisclaimer, hideDisclaimerModal} from "../actions";

const mapStateToProps = (state, props) => ({
    disclaimerModalShow: state.displayDisclaimerModal,
    disclaimer: state.disclaimer
})


function DisclaimerLong(props) {
    return (
        <Modal {...props} aria-labelledby="contained-modal-title-vcenter"  size={"lg"}>
            <Modal.Header closeButton>
                <Modal.Title id="contained-modal-title-vcenter">
                    Terms and conditions
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Container>
                    <div dangerouslySetInnerHTML={{__html: props.disclaimer}}/>
                </Container>
            </Modal.Body>
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
            <a href={"#"} id={"disclaimer"} onClick={this.props.displayDisclaimerModal}>TERMS AND CONDITIONS
            </a>
            <DisclaimerLong disclaimer={this.props.disclaimer} show={this.props.disclaimerModalShow}
                            onHide={() => this.props.hideDisclaimerModal()}/>
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