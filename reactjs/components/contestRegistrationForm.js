import React, {Component} from "react";
import {Button, Container, Form, Modal} from "react-bootstrap";
import axios from 'axios'
import {Typeahead} from 'react-bootstrap-typeahead';
import {ErrorMessage, Formik} from 'formik';
import {connect} from "react-redux";
import * as yup from 'yup';
import {Loading} from "./basicComponents";
import {contestRegistrationFormReturn} from "../actions";

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
            copilot: yup.string(),
            aircraft: yup.string().required(),
            club: yup.string().required(),
            airspeed: yup.number().required(),
        });
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

    handleSubmit(values, setSubmitting) {
        console.log("submitting")
        console.log(values)
        setSubmitting(false)
        // const res = await axios.post("", {})
    }

    render() {
        if (!this.state.aircraftOptions || !this.state.clubOptions) {
            return <Loading/>
        }
        let initialValues = {
            aircraftOptions: this.state.aircraftOptions,
            clubOptions: this.state.clubOptions,
            copilot: "",
            aircraft: "",
            club: "",
            airspeed: ""
        }
        if (this.props.participation) {
            initialValues.copilot = this.props.participation.team.crew.member2 ? this.props.participation.team.crew.member2.email : ""
            initialValues.aircraft = this.props.participation.team.aeroplane.registration
            initialValues.club = this.props.participation.team.club.name
            initialValues.airspeed = this.props.participation.air_speed
        }

        const formikProps = {
            initialValues: initialValues,
            validationSchema: this.schema,
            onSubmit: (formValues, {setSubmitting, setStatus, setErrors}) => {
                console.log("submit", formValues);
                setSubmitting(true);
                axios.post("/api/v1/contest/" + this.props.contestId + "/signup/").then((res) => {
                    setStatus("Registration successful")
                    this.props.contestRegistrationFormReturn()
                }).catch((e) => {
                    console.error(e);
                    setErrors({api: _.get(e, ["message"])})
                }).finally(() => {
                    setSubmitting(false);
                })

            }
        }

        return (
            <div>
                <h2>Register for contest {this.props.contest.name}</h2>
                <Formik {...formikProps}>
                    {props => (
                        <Form onSubmit={props.handleSubmit}>
                            <Form.Group>
                                <Form.Label>Co-pilot (optional)</Form.Label>
                                <Form.Control type={"email"} name={"copilot"} onChange={props.handleChange}
                                              value={props.values.copilot}
                                              isValid={props.touched.copilot && !props.errors.copilot}/>
                            </Form.Group>
                            <Form.Group>
                                <Form.Label>Aircraft</Form.Label>
                                <Typeahead id={"aircraft"} allowNew newSelectionPrefix={"Add new aircraft: "}
                                           name={"aircraft"}
                                           options={props.values.aircraftOptions}
                                           isInvalid={!!props.errors.aircraft}
                                           defaultSelected={[{label: props.initialValues.aircraft}]}
                                           onChange={e => props.setFieldValue("aircraft", e.length > 0 ? e[0].label : null)}/>
                                <ErrorMessage name={"aircraft"} component={"div"}/>
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
                                <Typeahead id={"club"} allowNew
                                           options={props.values.clubOptions}
                                           name={"club"}
                                           isInvalid={!!props.errors.club}
                                           defaultSelected={[{
                                               id: props.initialValues.club,
                                               label: props.initialValues.club
                                           }]}
                                           onChange={e => props.setFieldValue("club", e.length > 0 ? e[0].customOption ? e[0].label : e[0].id : null)}/>
                                <ErrorMessage name={"club"} component={"div"}/>
                            </Form.Group>
                            <Form.Group>
                                <Button variant="primary" type="submit" disabled={props.isSubmitting}>
                                    Register
                                </Button>
                                <Button variant={"danger"} type={"button"}
                                        onClick={() => this.props.contestRegistrationFormReturn()}>Cancel</Button>
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

const ContestRegistrationForm = connect(mapStateToProps,
    {
        contestRegistrationFormReturn
    }
)(ConnectedContestRegistrationForm)
export default ContestRegistrationForm