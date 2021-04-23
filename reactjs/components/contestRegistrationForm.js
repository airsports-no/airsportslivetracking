import React, {Component} from "react";
import {Button, Container, Form, Modal} from "react-bootstrap";
import axios from 'axios'
import {Typeahead} from 'react-bootstrap-typeahead';
import {ErrorMessage, Formik} from 'formik';
import {connect} from "react-redux";
import * as yup from 'yup';
import {Loading} from "./basicComponents";
import {contestRegistrationFormReturn, fetchMyParticipatingContests} from "../actions";
import {withRouter} from "react-router-dom";

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
        }
        this.schema = yup.object().shape({
            copilot_email: yup.string(),
            aircraft_registration: yup.string().required(),
            club_name: yup.string().required(),
            airspeed: yup.number().required(),
        });
    }

    handleSuccess() {
        this.props.fetchMyParticipatingContests()
        this.props.contestRegistrationFormReturn()
    }

    componentDidMount() {
        this.getClubOptions()
        this.getAircraftOptions()
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
        if (!this.state.aircraftOptions || !this.state.clubOptions) {
            return <Loading/>
        }
        let initialValues = {
            aircraftOptions: this.state.aircraftOptions,
            clubOptions: this.state.clubOptions,
            copilot_email: "",
            aircraft_registration: "",
            club_name: "",
            airspeed: ""
        }
        if (this.props.participation) {
            initialValues.copilot_email = this.props.participation.team.crew.member2 ? this.props.participation.team.crew.member2.email : ""
            initialValues.aircraft_registration = this.props.participation.team.aeroplane.registration
            initialValues.club_name = this.props.participation.team.club.name
            initialValues.airspeed = this.props.participation.air_speed
        }

        const formikProps = {
            initialValues: initialValues,
            validationSchema: this.schema,
            onSubmit: (formValues, {setSubmitting, setStatus, setErrors}) => {
                console.log("submit", formValues);
                setSubmitting(true);
                if (this.props.participation) {
                    formValues.contest_team = this.props.participation.id
                    axios.put("/api/v1/contests/" + this.props.contest.id + "/signup/", formValues).then((res) => {
                        setStatus("Registration successful")
                        if (!this.props.external) {
                            this.handleSuccess()
                        } else {
                            this.props.history.push("/participation/")
                        }
                    }).catch((e) => {
                        console.error(e);
                        setErrors({api: _.get(e, ["message"])})
                    }).finally(() => {
                        setSubmitting(false);
                    })

                } else {
                    axios.post("/api/v1/contests/" + this.props.contest.id + "/signup/", formValues).then((res) => {
                        setStatus("Registration successful")
                        if (!this.props.external) {
                            this.handleSuccess()
                        } else {
                            this.props.history.push("/participation/")
                        }
                    }).catch((e) => {
                        console.error(e);
                        setErrors({api: _.get(e, ["message"])})
                    }).finally(() => {
                        setSubmitting(false);
                    })
                }
            }
        }

        return (
            <div>
                {!this.props.participation ?
                    <h2>Register for {this.props.contest.name}</h2> :
                    <h2>Manage participation in {this.props.contest.name}</h2>}

                <Formik {...formikProps}>
                    {props => (
                        <Form onSubmit={props.handleSubmit} onAbort={() => this.props.history.push("/participation/")}>
                            <Form.Group>
                                <Form.Label>Co-pilot (optional)</Form.Label>
                                <Form.Control type={"email"} name={"copilot_email"} onChange={props.handleChange}
                                              value={props.values.copilot_email}
                                              isValid={props.touched.copilot_email && !props.errors.copilot_email}/>
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
                                <Button variant="primary" type="submit" disabled={props.isSubmitting}>
                                    Register
                                </Button>
                                <Button variant={"danger"} type={"button"}
                                        onClick={() => {
                                            if (!this.props.external) {
                                                this.props.contestRegistrationFormReturn()
                                            } else {
                                                this.props.history.push("/participation/")
                                            }
                                        }}>Cancel</Button>
                                {props.errors && _.has(props.errors, ["api"]) &&
                                <div className="text-danger">{_.get(props.errors, ["api"])}</div>}
                                {props.status && <div className="text-success">{props.status}</div>}
                            </Form.Group>
                        </Form>)}
                </Formik>
            </div>
        )
    }

}

const ContestRegistrationForm = withRouter(connect(mapStateToProps,
    {
        contestRegistrationFormReturn,
        fetchMyParticipatingContests
    }
)(ConnectedContestRegistrationForm))
export default ContestRegistrationForm