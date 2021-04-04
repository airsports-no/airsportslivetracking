import React, {Component} from "react";
import aboutPrecisionFlying from "./aboutTexts/aboutPrecisionFlying";
import aboutPilotPokerRun from "./aboutTexts/aboutPilotPokerRun";
import aboutANR from "./aboutTexts/aboutANR";
import AboutLogoPopup from "./aboutLogoPopup";

export default class AboutTaskPopup extends Component {
    render() {
        let text = null;
        if (this.props.navigationTask.contestant_set !== undefined) {
            if (this.props.navigationTask.scorecard !== undefined) {
                if (this.props.navigationTask.scorecard_data.task_type.includes("precision")) {
                    text = aboutPrecisionFlying(this.props.navigationTask.actual_rules, this.props.navigationTask.route.waypoints)
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("poker")) {
                    text = aboutPilotPokerRun
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("anr_corridor")) {
                    text = aboutANR(this.props.navigationTask.actual_rules)
                }
            }
        }
        return <AboutLogoPopup aboutText={text}/>
    }
}