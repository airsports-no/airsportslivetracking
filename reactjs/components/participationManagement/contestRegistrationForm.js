import React, {Component} from "react";
import {Button, Container, Form, Modal} from "react-bootstrap";
import axios from 'axios'
import {Typeahead} from 'react-bootstrap-typeahead';
import {ErrorMessage, Formik} from 'formik';
import {connect} from "react-redux";
import * as yup from 'yup';
import {Loading} from "../basicComponents";
import {fetchMyParticipatingContests} from "../../actions";
import {withParams} from "../../utilities";

axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'
const _ = require('lodash');
const mapStateToProps = (state, props) => ({})

class ConnectedContestRegistrationForm extends Component {
    constructor(props) {
        super(props)
        this.state = {
            aircraftOptions: null,
            clubOptions: null,
            personOptions: null
        }
        this.schema = yup.object().shape({
            copilot_id: yup.number().nullable(true),
            aircraft_registration: yup.string().required(),
            club_name: yup.string().required(),
            airspeed: yup.number().required(),
        });
    }

    handleSuccess(participationId) {
        this.props.fetchMyParticipatingContests()
        this.props.navigate("/participation/myparticipation/" + participationId + "/")
    }

    hideModal() {
        this.props.navigate("/participation/")
    }

    componentDidMount() {
        this.getClubOptions()
        this.getAircraftOptions()
        this.getPersonOptions()
    }

    getPersonOptions(part) {
        axios.get('/display/person/signuplist/').then((res) => {
            console.log(res)
            this.setState({
                personOptions: res.data.map((person) => {
                    return {
                        id: person.id,
                        label: person.first_name + " " + person.last_name + " (" + person.email + ")"
                    }
                })
            })
        })
    }


    getAircraftOptions(part) {
        axios.get('/api/v1/aircraft/').then((res) => {
            console.log(res)
            this.setState({
                aircraftOptions: res.data.map((aircraft) => {
                    return {label: aircraft.registration}
                })
            })
        })
    }


    getClubOptions(part) {
        axios.get('/api/v1/clubs/').then((res) => {
            this.setState({
                clubOptions: res.data.map((club) => {
                    return {id: club.name, label: club.name + " (" + club.country + ")"}
                })
            })
        })
    }

    render() {
        if (!this.state.aircraftOptions || !this.state.clubOptions || !this.state.personOptions) {
            return <Loading/>
        }
        let initialValues = {
            aircraftOptions: this.state.aircraftOptions,
            clubOptions: this.state.clubOptions,
            personOptions: this.state.personOptions,
            copilot_id: null,
            aircraft_registration: "",
            club_name: "",
            airspeed: ""
        }
        if (this.props.participation) {
            initialValues.copilot_id = this.props.participation.team.crew.member2 ? this.props.participation.team.crew.member2.id : null
            initialValues.aircraft_registration = this.props.participation.team.aeroplane.registration
            initialValues.club_name = this.props.participation.team.club.name
            initialValues.airspeed = this.props.participation.air_speed
        }

        const formikProps = {
            initialValues: initialValues,
            validationSchema: this.schema,
            onSubmit: (formValues, {setSubmitting, setStatus, setErrors}) => {
                let data = {
                    club_name: formValues.club_name,
                    aircraft_registration: formValues.aircraft_registration,
                    airspeed: formValues.airspeed,
                    copilot_id: formValues.copilot_id,
                }
                console.log("submit", data);
                setSubmitting(true);
                let method = "post"
                if (this.props.participation) {
                    method = "put"
                    data.contest_team = this.props.participation.id
                }
                axios({
                    method: method,
                    url: "/api/v1/contests/" + this.props.contest.id + "/signup/",
                    data: data
                }).then((res) => {
                    console.log("Response")
                    console.log(res)
                    setStatus("Registration successful")
                    this.handleSuccess(res.data.id)
                }).catch((e) => {
                    console.error(e);
                    console.log(e);
                    const errors = _.get(e, ["response", "data"])
                    if (Array.isArray(errors)) {
                        setErrors({api: errors})
                    } else {
                        setErrors(errors)
                    }
                }).finally(() => {
                    setSubmitting(false);
                })
            }
        }
        const form = <div>
            <Formik {...formikProps}>
                {props => (
                    <Form onSubmit={props.handleSubmit} onAbort={() => this.props.navigate("/participation/")}>
                        <Form.Group>
                            <Form.Label>Copilot (optional)</Form.Label>
                            <Typeahead id={"copilot_id"}
                                       newSelectionPrefix={"Select co-pilot: "}
                                       name={"copilot_id"}
                                       options={props.values.personOptions}
                                       isInvalid={!!props.errors.copilot_id}
                                       defaultSelected={props.initialValues.copilot_id ? [{
                                           id: this.props.participation.team.crew.member2.id,
                                           label: this.props.participation.team.crew.member2.first_name + " " + this.props.participation.team.crew.member2.last_name + " (" + this.props.participation.team.crew.member2.email + ")"
                                       }] : []}
                                       onChange={e => props.setFieldValue("copilot_id", e.length > 0 ? e[0].id : null)}/>
                            <ErrorMessage name={"copilot_id"} component={"div"}/>
                        </Form.Group>
                        <Form.Group>
                            <Form.Label>Aircraft</Form.Label>
                            <Typeahead id={"aircraft_registration"} allowNew
                                       newSelectionPrefix={"Add new aircraft: "}
                                       name={"aircraft_registration"}
                                       options={props.values.aircraftOptions}
                                       isInvalid={!!props.errors.aircraft_registration}
                                       defaultSelected={[{label: props.initialValues.aircraft_registration}]}
                                       onChange={e => props.setFieldValue("aircraft_registration", e.length > 0 ? e[0].label : null)}/>
                            <ErrorMessage name={"aircraft_registration"} component={"div"}/>
                        </Form.Group>
                        <Form.Group>
                            <Form.Label>Airspeed</Form.Label>
                            <Form.Control type={"number"} name={"airspeed"} onChange={props.handleChange}
                                          isInvalid={!!props.errors.airspeed} value={props.values.airspeed}
                            />
                            <ErrorMessage name={"airspeed"} component={"div"}/>

                        </Form.Group>
                        <Form.Group>
                            <Form.Label>Club</Form.Label>
                            <Typeahead id={"club_name"} allowNew
                                       options={props.values.clubOptions}
                                       name={"club_name"}
                                       isInvalid={!!props.errors.club_name}
                                       defaultSelected={[{
                                           id: props.initialValues.club_name,
                                           label: props.initialValues.club_name
                                       }]}
                                       onChange={e => props.setFieldValue("club_name", e.length > 0 ? e[0].customOption ? e[0].label : e[0].id : null)}/>
                            <ErrorMessage name={"club_name"} component={"div"}/>
                        </Form.Group>
                        <Form.Group>
                            <Button variant="success" type="submit" disabled={props.isSubmitting} style={{marginRight: "5px"}}>
                                Save
                            </Button>
                            {this.props.participation ?
                                <Button variant="primary" type="button" onClick={() => {
                                    this.props.navigate("/participation/myparticipation/" + this.props.participation.id + "/")
                                }}>
                                    Task details
                                </Button> : null}

                            {props.errors && _.has(props.errors, ["api"]) &&
                            <div className="text-danger">{_.get(props.errors, ["api"])}</div>}
                            {props.status && <div className="text-success">{props.status}</div>}
                        </Form.Group>
                    </Form>)}
            </Formik>
        </div>

        return (
            <Modal onHide={() => this.hideModal()}
                   show={true}
                   aria-labelledby="contained-modal-title-vcenter">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-vcenter">
                        {!this.props.participation ?
                            <h2>Register for {this.props.contest.name}</h2> :
                            <h3>Change registration details for '{this.props.contest.name}'</h3>}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body className="show-grid">
                    <Container>
                        {form}
                    </Container>
                </Modal.Body>
            </Modal>
        )
    }

}

const ContestRegistrationForm = connect(mapStateToProps,
    {
        fetchMyParticipatingContests
    }
)(ConnectedContestRegistrationForm)
export default withParams(ContestRegistrationForm)