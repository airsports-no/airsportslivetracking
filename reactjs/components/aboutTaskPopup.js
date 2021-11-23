import React, {Component} from "react";
import aboutPrecisionFlying from "./aboutTexts/aboutPrecisionFlying";
import aboutPilotPokerRun from "./aboutTexts/aboutPilotPokerRun";
import aboutANR from "./aboutTexts/aboutANR";
import AboutLogoPopup from "./aboutLogoPopup";
import aboutAirsports from "./aboutTexts/aboutAirsports";

export default class AboutTaskPopup extends Component {
    render() {
        let text = null, displaySecretGatesToggle=false;
        if (this.props.navigationTask.contestant_set !== undefined) {
            if (this.props.navigationTask.scorecard !== undefined) {
                if (this.props.navigationTask.scorecard_data.task_type.includes("precision")) {
                    text = aboutPrecisionFlying(this.props.navigationTask.actual_rules, this.props.navigationTask.route.waypoints)
                    displaySecretGatesToggle = true
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("poker")) {
                    text = aboutPilotPokerRun
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("anr_corridor")) {
                    text = aboutANR(this.props.navigationTask.actual_rules)
                }else if (this.props.navigationTask.scorecard_data.task_type.includes("airsports")) {
                    text = aboutAirsports(this.props.navigationTask.actual_rules, this.props.navigationTask.route.waypoints)
                    displaySecretGatesToggle = true
                }
            }
        }
        return <AboutLogoPopup aboutText={text} colour={"#e01b1c"} size={2} displaySecretGatesToggle={displaySecretGatesToggle}/>
    }
}