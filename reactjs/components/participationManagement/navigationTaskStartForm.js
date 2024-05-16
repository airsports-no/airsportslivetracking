import React, {Component} from "react";
import {Button, Col, Form, Row} from "react-bootstrap";
import axios from 'axios'
import {ErrorMessage, Formik} from 'formik';
import {connect} from "react-redux";
import * as yup from 'yup';
import {fetchMyParticipatingContests} from "../../actions";
import DatePicker from "react-datepicker";

import "react-datepicker/dist/react-datepicker.css";
import {withParams} from "../../utilities";


axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'
const _ = require('lodash');
const mapStateToProps = (state, props) => ({})

class ConnectedSelfRegistrationForm extends Component {
    constructor(props) {
        super(props)
        this.schema = yup.object().shape({
            starting_point_time: yup.string().required(),
        });
    }

    handleSuccess() {
        this.props.fetchMyParticipatingContests()
        this.props.navigate("/participation/myparticipation/" + this.props.participation.id + "/")

    }

    componentDidMount() {
    }


    render() {
        let today = new Date();
        today.setHours(today.getHours() + 1);
        let initialValues = {
            starting_point_time: today,
            wind_speed: 0,
            wind_direction: 0,
            adaptive_start: false
        }

        const formikProps = {
            initialValues: initialValues,
            validationSchema: this.schema,
            onSubmit: (formValues, {setSubmitting, setStatus, setErrors}) => {
                formValues.starting_point_time.setSeconds(0)
                let data = {
                    starting_point_time: formValues.starting_point_time.toISOString(),
                    contest_team: this.props.participation.id,
                    adaptive_start: formValues.adaptive_start,
                    wind_speed: formValues.wind_speed,
                    wind_direction: formValues.wind_direction
                }
                console.log("submit", data);
                setSubmitting(true);
                axios.put(document.configuration.navigationTaskContestantSelfRegistration(this.props.participation.contest.id, this.props.navigationTask.pk), data).then((res) => {
                    setStatus("Registration successful")
                    this.handleSuccess()
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

        return (
            <div>
                <h2>Set starting time for {this.props.navigationTask.name}</h2>

                <Formik {...formikProps}>
                    {props => (
                        <Form onSubmit={props.handleSubmit} onAbort={() => this.props.navigate("/participation/")}>
                            <Row>
                                <Col>
                                    <Form.Label>Starting point time: </Form.Label>&nbsp;
                                    <DatePicker
                                        selected={props.values.starting_point_time}
                                        name={"starting_point_time"}
                                        onChange={value => props.setFieldValue("starting_point_time", value)}
                                        showTimeSelect
                                        timeFormat="HH:mm"
                                        timeIntervals={1}
                                        timeCaption="time"
                                        dateFormat="MMMM d, yyyy HH:mm"
                                    />
                                    <ErrorMessage name={"starting_point_time"} component={"div"}/>
                                </Col>
                            </Row>
                            <Row>
                                <Col>
                                    <Form.Check name={"adaptive_start"} type={"checkbox"}
                                                onChange={props.handleChange}
                                                label={"Adaptive start"}
                                                defaultValue={props.initialValues.adaptive_start}/>
                                    <ErrorMessage name={"adaptive_start"} component={"div"}/>
                                </Col>
                            </Row>
                            <Row>
                                <Col>
                                    <Form.Text>If adaptive start is selected, your start time will be set to the nearest whole minute you
                                        cross the 10 NM long line going through the starting gate anywhere between one hour before and one hour after the selected starting
                                        point time (<a href={'https://home.airsports.no/faq/#adaptiv-start'}>FAQ</a>).</Form.Text>
                                </Col>
                            </Row>
                            <Row>
                                <Col>
                                    <Form.Label>Wind direction</Form.Label>
                                    <Form.Control name={"wind_direction"} type={"number"} placeholder={"Direction"}
                                                  onChange={props.handleChange}
                                                  defaultValue={props.initialValues.wind_direction}/>
                                    <ErrorMessage name={"wind_direction"} component={"div"}/>
                                </Col>
                                <Col>
                                    <Form.Label>Wind speed</Form.Label>
                                    <Form.Control name={"wind_speed"} type={"number"} placeholder={"Speed"}
                                                  onChange={props.handleChange}
                                                  defaultValue={props.initialValues.wind_speed}/>
                                    <ErrorMessage name={"wind_speed"} component={"div"}/>
                                </Col>
                            </Row>
                            <Row>
                                <Form.Text>After clicking "Register" you will receive an email with a link to an
                                    annotated navigation map that can be used to fly the task.</Form.Text>
                            </Row>
                            <Row>
                                <Button variant="primary" type="submit" disabled={props.isSubmitting}>
                                    Register
                                </Button>
                                <Button variant={"danger"} type={"button"}
                                        onClick={() => {
                                            this.props.navigate("/participation/myparticipation/" + this.props.participation.id + "/")
                                        }}>Cancel</Button>
                                {props.errors && _.has(props.errors, ["api"]) &&
                                <div className="text-danger">{_.get(props.errors, ["api"])}</div>}
                                {props.status && <div className="text-success">{props.status}</div>}
                            </Row>
                        </Form>)}
                </Formik>
            </div>
        )
    }

}

const SelfRegistrationForm = connect(mapStateToProps,
    {
        fetchMyParticipatingContests
    }
)(ConnectedSelfRegistrationForm)
export default withParams(SelfRegistrationForm)